import queue
import threading
import time


exitFlag = 0


class myThread (threading.Thread):
    def __init__(self, threadID, name, q, ql):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q
        self.ql = ql
        self.count = 5

    def run(self):
        print("Starting " + self.name)
        self.process_data(self.name, self.q, self.ql)
        print("Exiting " + self.name)

    def process_data(self, threadName, q, ql):
        while self.count:
            ql.acquire()
            if not q.empty():
                data = q.get()
                ql.release()
                print("%s processing %s" % (threadName, data))
            else:
                ql.release()
                time.sleep(1)
            self.count -= 1


def main():
    queueLock = threading.Lock()
    threadList = ["Thread-1", "Thread-2", "Thread-3"]
    nameList = ["One", "Two", "Three", "Four", "Five"]
    workQueue = queue.Queue(10)
    threads = []
    threadID = 1
    # Create new threads
    for tName in threadList:
        thread = myThread(threadID, tName, workQueue, queueLock)
        thread.start()
        threads.append(thread)
        threadID += 1

    # Fill the queue
    queueLock.acquire()
    for word in nameList:
        workQueue.put(word)
    queueLock.release()

    # Wait for queue to empty
    while not workQueue.empty():
        print()
        pass

    # Notify threads it's time to exit
    global exitFlag
    exitFlag = 1

    # Wait for all threads to complete
    for t in threads:
        t.join()
    print("Exiting Main Thread")


if __name__ == "__main__":
    main()
