from requests import get
import os
from shutil import rmtree
import re
import argparse
import ffmpeg
import time
import threading
import math


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
# ----------------common----------------------


class myThread (threading.Thread):
    def __init__(self, threadID, work, args):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.work = work
        self.args = args

    def run(self):
        print("Starting thread" + self.threadID)
        self.work(self.args)
        print("Exiting thread" + self.threadID)

# ----------------common----------------------


def clearTargetDir(target_dir_path, remove=False):
    rmtree(target_dir_path)
    if not remove:
        os.mkdir(target_dir_path)


# ----------------------before download-----------

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
    parser.add_argument('-s', dest='start', action='store',
                        type=int, help='which parts to start from', default=0)
    parser.add_argument('-c', dest='chunklist', action='store',
                        type=str, help='server chunklist for url')
    parser.add_argument('-t', dest='thread', action='store',
                        type=int, help='thread number', default=1)
    parser.add_argument('-m', dest='mode', action='store',
                        type=str, help='program mode', default='dm')  # d: download only, m: merge only, dm: download and merge

    args = parser.parse_args()
    checkArg(args)
    return args


# ----------------after download------------------


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


# ---------------- downloading -------------------
def compute_process():
    files = os.listdir(target_swap_dir)
    print('-->> {}%'.format(round(len(files)/total_count*10000)/100, 2))


def downloadParts(pid, url, own_swap_dir):

    if not os.path.exists(os.path.join(own_swap_dir, pid)):
        print('Downloading {} part'.format(pid))

        res = get(url, timeout=11, headers=header, proxies=proxies)
        if res.status_code == 200:
            tempfd = open(os.path.join(own_swap_dir, pid), 'wb')
            tempfd.write(res.content)
            compute_process()
        else:
            print('request not ok')
    else:
        print('XXX Skiping {} part'.format(pid))


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


def downloadAll(output, chunklist, start=0, thread=1, dl=True, mg=True):
    chunklist_file_path = os.path.join(
        chunklist_dir, output.replace('.mp4', '.m3u8'))
    if not os.path.exists(chunklist_file_path):
        downloadChunklistFile(chunklist, chunklist_file_path)

    prefix = chunklist[:chunklist.index('chunklist.m3u8')]
    queue = []
    temp_swap_dir = os.path.join(swap_dir, output.replace('.mp4', '_swap'))
    if not os.path.exists(temp_swap_dir):
        os.mkdir(temp_swap_dir)
    global target_swap_dir
    target_swap_dir = temp_swap_dir
    if dl:
        fd = open(chunklist_file_path, 'r')
        lines = fd.readlines()
        https = [prefix+i for i in lines if i.startswith('media_')]
        global total_count
        total_count = len(https)
        print('This Video chunklist.m3u8 has {} links:'.format(len(https)))
        count = start
        queue.extend(https[count:])
        lastReqUrl = None
        lastReqCounter = 0
        while(queue):
            url = queue.pop(0)
            if lastReqUrl != url:
                lastReqUrl = url
                lastReqCounter = 0
            else:
                lastReqCounter += 1

            if lastReqCounter > 10:
                print('Request {} too many times'.format(lastReqUrl))
                exit(-1)

            pidPattern = r"media_(?P<pid>\d*)."
            pid = re.search(pidPattern, url).group('pid')

            try:
                downloadParts(pid, url, temp_swap_dir)
            except Exception as exp:
                print(
                    'Having ERROR downloading parts {}, requeue this request'.format(pid))
                print(exp)
                queue.append(url)
                time.sleep(1.01)

    if mg:
        inter_file = os.path.join(inter_dir, output.replace('.mp4', '.input'))
        createInputFile(temp_swap_dir, inter_file)
        temp_dir = output[:output.index('_')]
        output = output[output.index('_')+1:]
        if not os.path.exists(os.path.join(done_dir, temp_dir)):
            os.mkdir(os.path.join(done_dir, temp_dir))
        output_file = os.path.join(done_dir, temp_dir, output)
        genOutputFile(inter_file, output_file)
        clearTargetDir(temp_swap_dir, remove=True)


# -------------------------main -------------------------

def main():
    args = parseArg()
    print(args)
    if args.mode == 'dm':
        print('dm mode')
        downloadAll(args.outputfile,
                    args.chunklist, args.start, args.thread)
    elif args.mode == 'd':
        print('d mode')
        downloadAll(args.outputfile,
                    args.chunklist, args.start, args.thread, mg=False)
    elif args.mode == 'm':
        print('m mode')
        downloadAll(args.outputfile,
                    args.chunklist, args.start, args.thread, dl=False)
    else:
        print('mode error')


if __name__ == "__main__":
    main()
