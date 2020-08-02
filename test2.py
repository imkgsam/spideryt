#!/usr/bin/python3

import math
import ffmpeg
import argparse
import re
from shutil import rmtree
import os
from requests import get
import queue
from test import main
import threading
import time
import random

exitFlag = 0

swap_dir = 'C:\\Users\\speng\\code_base\\youtuber\\swap'
inter_dir = 'C:\\Users\\speng\\code_base\\youtuber\\inter'
done_dir = 'C:\\Users\\speng\\code_base\\youtuber\\done'
chunklist_dir = 'C:\\Users\\speng\\code_base\\youtuber\\chunklist'

header = {
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'zh-CN,zh;q=0.9',
    'origin': 'https://www.ifvod.tv',
    'referer': 'https://www.ifvod.tv/play?id=6BHmahBMEJ0',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'}

proxies = {
    'http': 'socks5://127.0.0.1:10086',
    'https': 'socks5://127.0.0.1:10086',
}
total_count = 0
target_swap_dir = None


class myThread (threading.Thread):
    def __init__(self, threadID, name, q, ql, temp_swap_dir):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q
        self.ql = ql
        self.count = 0
        self.fail = 0
        self.temp_swap_dir = temp_swap_dir

    def run(self):
        print("Starting " + self.name)
        self.process_data()
        print("Exiting " + self.name)

    def process_data(self):
        while not exitFlag:
            self.ql.acquire()
            if not self.q.empty():
                url = self.q.get()
                self.ql.release()
                pidPattern = r"media_(?P<pid>\d*)."
                pid = re.search(pidPattern, url).group('pid')
                try:
                    print("{} downloading {}".format(self.name, pid))
                    downloadParts(pid, url, self.temp_swap_dir)
                    self.count += 1
                    time.sleep(random.randint(0, 2)+random.randint(1, 99)/100)

                except Exception as exp:
                    print(
                        'Having ERROR downloading parts {}, requeue this request'.format(pid))
                    print(exp)
                    self.q.put(url)
                    self.fail += 1
                    time.sleep(random.randint(0, 5)+random.randint(1, 99)/100)
            else:
                self.ql.release()
        print('***********{} processed {} tasks failed {} times*************'.format(
            self.name, self.count, self.fail))


def clearTargetDir(target_dir_path, remove=False):
    rmtree(target_dir_path)
    if not remove:
        os.mkdir(target_dir_path)


def checkArg(args):
    if not args.outputfile:
        print('missing output file')
        exit(-1)
    if not args.chunklist:
        print('missing chunklist')
        exit(-1)


def parseArg():
    parser = argparse.ArgumentParser(description='Process input parameters.')
    parser.add_argument('-o', dest='outputfile', action='store',
                        type=str, help='input files(*.mp4)')
    parser.add_argument('-c', dest='chunklist', action='store',
                        type=str, help='server chunklist for url')
    parser.add_argument('-t', dest='thread', action='store',
                        type=int, help='thread number', default=1)

    args = parser.parse_args()
    checkArg(args)
    return args


def createInputFile(parts_dir_path, inter_file):
    if os.path.exists(inter_file):
        print('output file exist')
        return -1
    if not os.path.exists(parts_dir_path):
        print('intput dir not exist')
        return -1
    parts = os.listdir(parts_dir_path)
    if len(parts) == 0:
        print('input dir has not files')
        return -1
    parts = list(map(lambda x: int(x), parts))
    parts.sort()
    print(parts)

    outputfd = open(inter_file, 'a')

    for i in parts:
        p = '{}\{}'.format(parts_dir_path, i)
        outputfd.write('file {}\n'.format(p.replace('\\', '\\\\')))
    outputfd.close()


def genOutputFile(inter_file, output_file):
    if not os.path.exists(inter_file):
        print('inter file not exist')
        return -1
    (
        ffmpeg
        .input(inter_file, format='concat', safe=0)
        .output(output_file, c='copy')
        .run()
    )


def compute_process(target_swap_dir):
    files = os.listdir(target_swap_dir)
    print('-->> {}%\n'.format(round(len(files)/total_count*10000)/100, 2))


def downloadParts(pid, url, own_swap_dir):

    if not os.path.exists(os.path.join(own_swap_dir, pid)):
        res = get(url, timeout=11, headers=header, proxies=proxies)
        if res.status_code == 200:
            tempfd = open(os.path.join(own_swap_dir, pid), 'wb')
            tempfd.write(res.content)
            compute_process(own_swap_dir)
        else:
            print('request not ok')
    else:
        print('XXX Skiping {} part\n'.format(pid))


def downloadChunklistFile(chunklist_url, chunklist_file_path):
    print('Downloading chunklist file')
    retry = 10
    timeout = 5
    if os.path.exists(chunklist_file_path):
        print('chunkfile already exist. continue.......')
        return
    while retry > 0:
        try:
            res = get(chunklist_url, timeout=timeout,
                      headers=header, proxies=proxies)
            if res.status_code == 200:
                with open(chunklist_file_path, 'wb') as tempfd:
                    tempfd.write(res.content)
                    print('chunklist file Save OK!!')
                return
        except Exception as exp:
            print('failed to download chunklist file, retrying........')
            timeout = math.ceil(timeout*1.1)
            retry -= 1
    print('fail to download chunkfile. exiting.......')
    exit(-1)


def downloadAll(output, chunklist, thread=1):
    # create
    chunklist_file_path = os.path.join(
        chunklist_dir, output.replace('.mp4', '.m3u8'))
    if not os.path.exists(chunklist_file_path):
        downloadChunklistFile(chunklist, chunklist_file_path)

    prefix = chunklist[:chunklist.index('chunklist.m3u8')]
    temp_swap_dir = os.path.join(swap_dir, output.replace('.mp4', '_swap'))
    if not os.path.exists(temp_swap_dir):
        os.mkdir(temp_swap_dir)

    fd = open(chunklist_file_path, 'r')
    lines = fd.readlines()
    https = [prefix+i for i in lines if i.startswith('media_')]
    global total_count
    total_count = len(https)
    print('This Video chunklist file has {} links:'.format(len(https)))

    queueLock = threading.Lock()
    workQueue = queue.Queue(len(https))
    threads = []
    threadID = 1
    threadList = ['Thread-'+str(i) for i in range(thread)]

    # Fill the queue
    time1 = time.time()
    queueLock.acquire()
    for url in https:
        workQueue.put(url)
    queueLock.release()
    time2 = time.time()

    # Create new threads
    for tName in threadList:
        thread = myThread(threadID, tName, workQueue, queueLock, temp_swap_dir)
        threads.append(thread)
        thread.daemon = True
        thread.start()

        threadID += 1

    # busy looping until queue is emptied
    while not workQueue.empty():
        pass

    global exitFlag
    exitFlag = 1

    for t in threads:
        t.join()
    time3 = time.time()

    inter_file = os.path.join(inter_dir, output.replace('.mp4', '.input'))
    createInputFile(temp_swap_dir, inter_file)
    temp_dir = output[:output.index('_')]
    if not os.path.exists(os.path.join(done_dir, temp_dir)):
        os.mkdir(os.path.join(done_dir, temp_dir))
    output_file = os.path.join(done_dir, temp_dir, output[output.index('_'):])
    genOutputFile(inter_file, output_file)
    clearTargetDir(temp_swap_dir, remove=True)
    time4 = time.time()

    print('enqueue time is {}\nprocess time is {}\nmerge time is {}\ntotal time is {}\n'.format(
        time2-time1, time3-time2, time4-time3, time4-time1))


def main():
    args = parseArg()
    print(args)

    downloadAll(args.outputfile, args.chunklist, args.thread)


# def task(threadNumber):
#     threadList = ['Thread-'+str(i) for i in range(threadNumber)]
#     nameList = [i for i in range(25)]
#     queueLock = threading.Lock()
#     workQueue = queue.Queue(25)
#     threads = []
#     threadID = 1

#     # Fill the queue
#     time1 = time.time()
#     queueLock.acquire()
#     for word in nameList:
#         workQueue.put(word)
#     queueLock.release()
#     time2 = time.time()

#     # Create new threads
#     for tName in threadList:
#         thread = myThread(threadID, tName, workQueue, queueLock)
#         thread.start()
#         threads.append(thread)
#         threadID += 1

#     while not workQueue.empty():
#         pass
#     print('here')
#     global exitFlag
#     exitFlag = 1
#     for t in threads:
#         t.join()
#     time3 = time.time()
#     print("Exiting Main Thread")
#     print('enqueue time is {}\nprocess time is {}\ntotal time is {}'.format(
#         time2-time1, time3-time2, time3-time1))
if __name__ == "__main__":
    main()
