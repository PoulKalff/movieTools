#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import curses
import signal
import shutil
import locale
import shutil
import argparse
import datetime
import subprocess
import logging as log

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

version = "v1.0"   # first complete version

# --- Variables ----------------------------------------------------------------------------------

acceptedFiles = ['.TS', '.MKV', '.SRT', '.MP4']

extJobs = {   1 : "ccextractor -o '%s' -tpage %s '%s'",     # (outputFile, textTV_page, inputFile)   # side 398
              3 : "mkvmerge -o '%s' --split parts:%s-%s '%s'", # (outputfile, cut_from_time, cut_to_time, inputfile)
              4 : "HandBrakeCLI -e x264  -q 20.0 -a 1 -E ffaac -B 160 -6 dpl2 -R Auto -D 0.0 --audio-copy-mask aac,ac3,dtshd,dts,mp3 --audio-fallback ffac3 -f mkv --loose-anamorphic --modulus 2 -m --x264-preset veryfast --h264-profile main --h264-level 4.0 -o '%s' -i '%s'",     # (Inputfile, outputfile)
            4.1 : " --srt-file '%s' --srt-codeset UTF-8"
          }

# --- Functions ----------------------------------------------------------------------------------

def getFileOut(fileName, opr, newExt, newDir):
    """ Formats filename to be used as output. Optional jobType Description is added to name """
    path, fil = os.path.split(fileName)
    name, ext = fil.rsplit('.', 1)
    operation = opr if opr else ''
    outPath = newDir if newDir else path
    extension = newExt if newExt else ext
    return os.path.join(outPath, name) + operation + '.' + extension

def runExternal(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, stderr=open(os.devnull, 'w'))
    output, err = process.communicate()
    return output

def checkPackage(package):
    if ' ' in package:
        return -1       # Please specify one pacakge only
    raw_output = runExternal("dpkg -l " + package)
    lines = raw_output.split('\n')
    if len(lines) == 1:
        return False
    else:
        return True

# --- Classes --------------------------------------------------------------------------------------

class SubtitlePost:
    """ Represents one post in an .srt-file """

    def __init__(self, parent, post):
        # format nr-line
        if not post[0].isdigit():
            self.valid = False
        else:
            self.nr = post[0]
        # format time-line
        if not '-->' in post[1]:
            self.valid = False
        else:
            self.valid = True
            fra, til = post[1].split('-->')
            if parent.negative:
                oFra = parent.createTimeObject(fra.strip()) - parent.displacement
                oTil = parent.createTimeObject(til.strip()) - parent.displacement
            else:
                oFra = parent.createTimeObject(fra.strip()) + parent.displacement
                oTil = parent.createTimeObject(til.strip()) + parent.displacement
            if oFra < parent.zero:
                self.valid = False
            if parent.max and oTil > parent.max:
                self.valid = False
            if self.valid:
                self.tidFra = parent.formatTime(oFra)
                self.tidTil = parent.formatTime(oTil)
        # format text-line(s)
        self.textLinier = False
        if len(post[2:]) == 2:
            if len(post[2]) < 30 and len(post[3]) < 30:
                self.textLinier = [post[2] + ' ' + post[3]]
        elif len(post[2:]) == 3:
            if len(post[2]) < 20 and len(post[3]) < 20 and len(post[4]) < 20:
                alText = (post[2] + ' ' + post[3] + ' ' + post[4]).split(' ')
                superLine = ' '.join(alText)
                midtSpace = superLine.find(' ', len(superLine) / 2)
                self.textLinier = [superLine[:midtSpace], superLine[midtSpace:]]
        if not self.textLinier: # if no value given above
            self.textLinier = post[2:]


    def show(self):
        print self.nr
        print self.tidFra, '-->', self.tidTil
        for l in self.textLinier:
            print l


    def toFile(self, postNr=False):
        ud = str(postNr) if postNr else str(self.nr)
        ud += '\n' + self.tidFra + ' --> ' + self.tidTil + '\n'
        for l in self.textLinier:
            ud += l + '\n'
        ud += '\n'
        return ud


class HandleSubtitles:
    """ Displaces time and shortens length of an .srt-file """

    def __init__(self, filename, dsp, max, negative):
        self.posts = []
        self.file = filename
        rawData = self.readFile()
        rawData = rawData.replace('\xef\xbb\xbf', '')   # BOM
        rawData = rawData.replace('\r','')
        self.displacement = self.createTimeObject(dsp)
        self.zero = self.createTimeObject('00:00:00.000')
        self.max = self.createTimeObject(max) if max != '00:00:00' else False
        self.negative = False if negative == 'False' else True
        self.processPosts(rawData.split('\n'))
        self.writeFile()


    def processPosts(self, data):
        """ builds all data into posts and displaces time """
        p = []
        for linie in data:
            l = linie.strip()
            if l == '':
                if p != []:
                    self.posts.append(SubtitlePost(self, p))
                    p = []
            else:
                p.append(l)


    def formatTime(self, ind):
        """ Tager deltatime, formaterer og returnerer string """
        timeString = str(ind)
        if '.' in timeString:
            hms, ms = str(timeString).split('.')
        else:
            hms = timeString
            ms = '0'
        if len(hms) < 8:
            hms = '0' + hms
        ms += '000'
        return hms + ',' + ms[:3]


    def createTimeObject(self, ind):
        """ Tager string og konverterer til timedelta-object """
        # miliseconds
        if '.' in ind:
            _rest, ml = ind.split('.')
        elif ',' in ind:
            _rest, ml = ind.split(',')
        else:
            ml = '00'
            _rest = ind
        # seconds
        if ':' in _rest:
            _rest, s = _rest.rsplit(':', 1)
        else:
            s = _rest
            _rest = False
        # minutes
        if _rest and ':' in _rest:
            _rest, m = _rest.rsplit(':', 1)
        elif _rest:
            m = _rest
            _rest = False
        else:
            m = '00'
        # hours
        if _rest and ':' in _rest:
            _rest, h = _rest.rsplit(':', 1)
        elif _rest:
            h = _rest
            _rest = False
        else:
            h = '00'
        return datetime.timedelta(hours=float(h), minutes=float(m), seconds=float(s), milliseconds=float(ml))


    def readFile(self):
        f = open(self.file,'r')
        data = f.read()
        f.close()
        return data


    def writeFile(self):
        # make backup
        counter = 0
        while os.path.exists(self.file + '_BACKUP' + str(counter)):
            counter += 1
        shutil.copy(self.file, self.file + '_BACKUP' + str(counter))
        # write file
        nr = 0
        f = open(self.file, 'w')
        for p in self.posts:
            if p.valid:
                nr += 1
                f.writelines(p.toFile(nr))
        f.close()


class FlipSwitch():
    # (NEW) Represents a switch with on and off-state

    def __init__(self, Ind):
        self._value = bool(Ind)

    def flip(self):
        if self._value == True:
            self._value = False
        else:
            self._value = True

    def get(self):
        return self._value

    def getString(self):
        return str(self._value)


class RangeIterator():
    # (NEW) Represents a range of INTs from 0 -> X

    def __init__(self, Ind, loop=True):
        self.current = 0
        self.max = Ind
        self.loop = loop

    def inc(self, count=1):
        self.current += count
        self._test()

    def dec(self, count=1):
        self.current -= count
        self._test()

    def _test(self):
        if self.loop:
            if self.current > self.max:
                self.current -= self.max + 1
            elif self.current < 0:
                self.current += self.max + 1
        elif not self.loop:
            if self.current >= self.max:
                self.current = self.max
            elif self.current < 0:
                self.current = 0

    def get(self):
        return self.current

class Packages:
    """ Status of installed packages """

    ccextractor = False
    handbrake = False
    mkvmerge = False
    vlc = False



class File:
    """ Holds EACH file to process """

    def __init__(self, no, fileIn, xPos, col):
        self.no = no
	self.path, self.name = os.path.split(os.path.abspath(fileIn))
        self.xPos = xPos
        self.color = col


class Job:
    """ Holds EACH job to process """

    def __init__(self, fileNr, opr, arg1=None, arg2=None, arg3=None):
        self.fileIndex = fileNr
        self.operation = opr
        self.argument1 = arg1
        self.argument2 = arg2
        self.argument3 = arg3
        if opr == 1:
            self.displayName = 'Extract ttpage %s' % (arg1)
        elif opr == 2:
            direction = '-->' if arg3.startswith('True') else '<--'
            self.displayName = 'Shift CC %s (%s), Capped at %s' % (arg1, direction, arg2)
        elif opr == 3:
            self.displayName = 'Slice: (%s --> %s)' % (arg1, arg2)
        elif opr == 4:
            self.displayName = 'Compress file (and add CC, if any)'

    def __str__(self):
        """ Enables sorting/comparison of jobs """
        return str(self.__dict__)

    def __eq__(self, other):
        """ Enables sorting/comparison of jobs """
        return self.__dict__ == other.__dict__


class SubMenu:
    """ A SubMenu object """

    def __init__(self, ID, xPos, yPos, items, pointer):
        self.ID = ID
        self.x = xPos
        self.y = yPos
        self.menuItems = items
        self.highlighted =  None
        self.prevPointer = pointer

    def getCoords(self):
        return (self.x, self.y)


class MovieTools_Model:
    """ Carries out actions, requested by the user through the calling class """

    def __init__(self, parent):
        self.parent = parent
        self.screen = parent.screen
        self.logEntry(1, 'MovieTools.py started')


    def logEntry(self, level, msg):
        """ Tilfoejer entry til log-filen. Fejler SILENTLY hvis filen ikke kan oprettes (pga. manglende rettigheder). """
        if not os.access('/var/log/movieTools.log', os.W_OK):
            return 0
        else:
            logLevel = ['NONE', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            ts = datetime.datetime.now().strftime('%Y-%m-%d|%H:%M:%S')
            fh = open("/var/log/movieTools.log", "a")
            if msg.endswith('started'):
                fh.write('\n')
            fh.write(ts + " " + logLevel[level] + " " + msg + "\n");
            fh.close();
            return 1;


    def boolEdit(self, value, xPos, yPos):
        """ Edits date within the screen by capturing all input"""
        bValue = 0 if value == 'False' else 1
        pointer = FlipSwitch(bValue)
        teRunning = True
        height, width = self.parent.screen.getmaxyx()
        self.screen.addstr(height - 1, 0, 'UP/DOWN changes state, ENTER accepts changes', curses.color_pair(6))    # Overwrite Status
        while teRunning:
            self.screen.addstr(yPos + 4, xPos + 10, pointer.getString() + ' ', curses.color_pair(5))
            self.screen.refresh()
            keyPressed = self.screen.getch()
            if keyPressed == 259 or keyPressed == 258:             # Cursor UP / Down
                pointer.flip()
            elif keyPressed == 260:           # Cursor LEFT
                teRunning = False
            elif keyPressed == 10:           # Return (Select)
                teRunning = False
        strValue = pointer.getString()
        returnValue = strValue + ' ' if len(strValue) == 4 else strValue
        return returnValue


    def timeEdit(self, eString, xPos, yPos):
        """ Edits date within the screen by capturing all input"""
        pointer = RangeIterator(len(eString) - 1, False)
        keyPressed = ''
        teRunning = True
        height, width = self.parent.screen.getmaxyx()
        self.screen.addstr(height - 1, 0, 'UP/DOWN cycles digit, ENTER accepts changes', curses.color_pair(6))    # Overwrite Status
        while teRunning:
            stringSliced = [eString[:pointer.get()], eString[pointer.get()], eString[pointer.get() + 1:]]
            self.screen.addstr(yPos + 4, xPos + 10, stringSliced[0], curses.color_pair(5))
            self.screen.addstr(yPos + 4, xPos + 10 + len(stringSliced[0]), stringSliced[1], curses.color_pair(1))
            self.screen.addstr(yPos + 4, xPos + 10 + len(stringSliced[0]) + len(stringSliced[1]), stringSliced[2], curses.color_pair(5))
            self.screen.addstr(yPos + 4, xPos + 10 + len(stringSliced[0]) + len(stringSliced[1]) + len(stringSliced[2]), ' ', curses.color_pair(0))    # overwrite last char
            #self.screen.addstr(yPos + 6, xPos + 10, str(stringSliced) + ' - ' + str(keyPressed), curses.color_pair(0))      # Message output
            self.screen.refresh()
            keyPressed = self.screen.getch()
            focusedChar = int(stringSliced[1])
            if keyPressed == 259:             # Cursor UP
                if focusedChar < 9:
                    stringSliced[1] = str(focusedChar + 1)
            elif keyPressed == 258:           # Cursor DOWN
                if focusedChar > 0:
                    stringSliced[1] = str(focusedChar - 1)
            if keyPressed == 261:           # Cursor RIGHT
                pointer.inc()
                if len(stringSliced[2]) > 0 and stringSliced[2][0] == ':':
                    pointer.inc()
            elif keyPressed == 260:           # Cursor LEFT
                if pointer.get() == 0:
                    returnFile = stringSliced[0] + stringSliced[1] + stringSliced[2]
                    teRunning = False
                else:
                    pointer.dec()
                    if len(stringSliced[0]) > 0 and stringSliced[0][-1] == ':':
                        pointer.dec()
            elif keyPressed == 10:           # Return (Select)
                returnFile = stringSliced[0] + stringSliced[1] + stringSliced[2]
                teRunning = False
            elif keyPressed > 47 and keyPressed < 58:   # 0-9
                stringSliced[1] = chr(keyPressed)
                pointer.inc()
                if len(stringSliced[2]) > 0 and stringSliced[2][0] ==  ':':
                    pointer.inc()
            eString = stringSliced[0] + stringSliced[1] + stringSliced[2]
        return returnFile


    def moveFile(self, scr, dst):
        # make sure source exists
        if os.path.exists(scr):
            os.chmod(scr, 0777)
        else:
            self.logEntry(4, '\nSource File does not exist, cannot contine')
            sys.exit('Fatal error in moveFile(), source does not exist: ' + scr)
        # make sure destination does not exist
        propDest = os.path.join(dst, os.path.split(scr)[1])
        if os.path.exists(propDest):
            counter = 0
            while os.path.exists(propDest + '_BACKUP' + str(counter)):
                counter += 1
            cleanName = propDest.split('_BACKUP')[0]
            shutil.move(propDest, cleanName + '_BACKUP' + str(counter))
        # move file
        shutil.move(scr, dst)
        return True


    def processJobs(self):
        """ Process list of jobs, one by one """
        previous = 100
        jobList = self.parent.jobs
        height, width = self.screen.getmaxyx()
        self.screen.clear()
        self.screen.addstr(1, 0, 'Processing ' + str(len(jobList)) + ' batch job' + ('s' if len(jobList) > 1 else '') + '....', curses.color_pair(0))
        out, lineOut, lineNr = '', '', 1
        for jobNr, job in enumerate(jobList):
            oFile = self.parent.files[job.fileIndex]
            fileIn = os.path.join(oFile.path, oFile.name)
            # check/reset stack
            if job.fileIndex != previous:
                previous = job.fileIndex
                stack = {'srt' : None, 'cmp' : None, 'cut' : None, 'cut_from' : None}
            # determine job type
            if job.operation == 1:
                srt_file = getFileOut(fileIn, None, 'srt', '/tmp')
                cmdLine = extJobs[1] % (srt_file, job.argument1, fileIn)
                stack['srt'] = srt_file
            if job.operation == 2:
                cmdLine = None
                if fileIn.endswith('.srt'):
                    fileToMove = fileIn
                elif stack['srt']:
                    fileToMove = stack['srt']
                if fileToMove:
                    self.logEntry(1, 'Started processing job ' + str(jobNr + 1))
                    self.screen.addstr(2 + lineNr, 0, '------ Running job ' + str(jobNr + 1) + ' of ' + str(len(self.parent.jobs)) + ': (Shift) ------------------', curses.color_pair(0))
                    oHS = HandleSubtitles(fileToMove, job.argument1, job.argument2, job.argument3)
                    direction = '-->' if job.argument3.startswith('True') else '<--'
                    self.screen.addstr(3 + lineNr, 0, 'CC shifted %s (%s), capped at %s' % (job.argument1, direction, job.argument2), curses.color_pair(0))
                    self.screen.addstr(4 + lineNr, 0, '------ Job #' +  str(jobNr + 1) + ' done! ' + '-----------------------------------', curses.color_pair(0))
                    self.logEntry(1, 'Finished processing job ' + str(jobNr + 1))
                    lineNr = lineNr + 4 if (lineNr + 4) < height else 4
            if job.operation == 3:
                cut_file = getFileOut(fileIn, '_cut', 'mkv', '/tmp')
                cmdLine = extJobs[3] % (cut_file, job.argument1, job.argument2, fileIn)
                stack['cut'] = cut_file
            if job.operation == 4:
                fil = stack['cut'] if stack['cut'] else fileIn
                cmp_file = getFileOut(fil, '_cmp', 'mkv', '/tmp')
                cmdLine = extJobs[4] % (cmp_file, fil)
                stack['cmp'] = cmp_file
                if stack['srt']:
                    cmdLine += extJobs[4.1] % (stack['srt'])
            # process command, if any
            if cmdLine:
                process = subprocess.Popen(cmdLine, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                self.logEntry(1, 'Started processing job ' + str(jobNr + 1))
                self.screen.addstr(2 + lineNr, 0, '------ Running job ' + str(jobNr + 1) + ' of ' + str(len(self.parent.jobs)) + ': (' + job.displayName.split()[0] + ') ------------------', curses.color_pair(0))
                while not (out == '' and process.poll() != None):
                    out = process.stdout.read(1)
                    if out == '\n':
                        if args.verbose:
                            self.screen.addstr(3 + lineNr, 1, '  ' + lineOut + '  ', curses.color_pair(0))
                            self.screen.refresh()
                            lineNr += 1
                        lineOut = ''
                    elif out == '%':
                        lineOut += '%  '
                        self.screen.addstr(3 + lineNr, 1, '  ' + lineOut + '  ', curses.color_pair(0))
                        self.screen.refresh()
                        lineOut = ''
                    else:
                        lineOut += out
                self.screen.addstr(4 + lineNr, 0, '------ Job #' +  str(jobNr + 1) + ' done! ' + '-----------------------------------', curses.color_pair(0))
                self.logEntry(1, 'Finished processing job ' + str(jobNr + 1))
                lineNr = lineNr + 4 if (lineNr + 4) < height else 4
            if (jobNr + 1) == len(jobList) or job.fileIndex != jobList[jobNr + 1].fileIndex:
                self.screen.addstr(2 + lineNr, 0, '  All jobs processed for "' + oFile.name + '", doing cleanup......', curses.color_pair(0))
                self.screen.refresh()
                # identify last modified file and move it back
                ending = ''
                finalFile = False
                if stack['srt']:
                    finalFile = stack['srt']
                    ending = '_TXT'
                    extension = 'srt'
                if stack['cut']:
                    finalFile = stack['cut']
                    ending += '_CUT'
                    extension = 'mkv'
                if stack['cmp']:
                    finalFile = stack['cmp']
                    ending += '_CMP'
                    extension = 'mkv'
                outDir = args.outdir if args.outdir else self.parent.rootPath
                if finalFile:
                    self.moveFile(finalFile, getFileOut(fileIn, ending, extension, outDir))
                self.screen.addstr(3 + lineNr, 10, 'Cleanup complete, processed file moved to "%s"' % (outDir), curses.color_pair(0))
                self.screen.refresh()
        if args.shutdown:
            runExternal("sudo init 0")
        else:
            self.screen.addstr(4 + lineNr, 0, '  All files processed, press any key to end program', curses.color_pair(0))
            self.screen.refresh()
            self.screen.getch()
            self.parent.killScreen()
            self.logEntry(1, str(len(jobList)) + ' jobs processed successfully')
            self.logEntry(1, 'Program terminated normally')
            sys.exit('\n' + str(len(jobList)) + ' jobs processed, terminating normally\n')



class MovieTools_View:
    """ Presents the screen of a program (mViewC) """

    def __init__(self, files):
        # Start en screen op
        self.screen = curses.initscr()
        self.screen.border(0)
        self.screen.keypad(1)
        curses.noecho()
        curses.start_color()
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLUE)
        self.displayInstr = False
        self.files = []
        for no, f in enumerate(files):
            self.files.append(File(no, f, no + 3, (no % 2) + 2))
        self.jobs = []
        self.rootPath = os.getcwd()
        self.tools = MovieTools_Model(self)
        self.pointer = RangeIterator(len(self.files) - 1, False)
        self.subMenus = []
        self.status = 'INIT'
        self.running = True
        self.loop()


    def loop(self):
        while self.running:
            self.displayScreen()
            self.getInput()
        self.killScreen()
        self.tools.logEntry(1, 'Program terminated by user')
        sys.exit('\n Program terminated by user\n')


    def killScreen(self):
        # Set everything back to normal
        self.screen.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()


    def displayScreen(self):
        """ handles resize and displays the data in "data" """
        height, width = self.screen.getmaxyx()
        data = self.createFrame()
        data += self.createText()
        if self.displayInstr:
            # Calculate center
            xCord = width / 2 - 19
            yCord = self.subMenus[-1].y + 4
            data += self.drawInstructions(xCord, yCord)
        for objMenu in self.subMenus:
            data += self.drawSubMenu(objMenu)
        data += self.updateStatus()
        self.screen.clear()
        # check if resized
        if curses.is_term_resized(height, width):
            curses.resizeterm(height, width)
        # paint window
        if height > 5 and width > 90:    # Match text when populated
            for x, y, text, color in data:
                if x < height and (y + len(text.decode('UTF-8')) <= width):         # check each line's data
                    self.screen.addstr(x, y, str(text), curses.color_pair(color))
        elif height > 1 and width > 5:
            self.screen.addstr(0, 0, "Window not displayed", curses.color_pair(1))
        self.screen.refresh()


    def moveFiles(self, startFrom, negative=False):
        """ moves all files below startFrom one line down """
        for no, f in enumerate(self.files):
            if f.no >= startFrom:
                if negative:
                    self.files[no].xPos -= 1
                else:
                    self.files[no].xPos += 1


    def createText(self):
        """ Creates the data used for painting the text """
        screenData = []
        height, width = self.screen.getmaxyx()
        cPos = (width - 1) / 2
        # headlines
        screenData.append([1, 2, 'Media Files:', 0])
        screenData.append([1, cPos + 2, 'Jobs:', 0])
        hFiles, hJobs = 0, 0
        for f in self.files:
            if f.xPos < height - 2:
                displayedName = '[<--] ' + f.name[len(f.name) - cPos + 10:] if len(f.name) > cPos - 2 else f.name
                highLighted = self.pointer.get() if not self.subMenus else self.subMenus[0].prevPointer.get()
                col = 1 if f.no == highLighted else f.color
                if f.xPos > 2:
                    screenData.append([f.xPos, 2, displayedName + ' ' + str(f.xPos), col])
            else:
                hFiles += 1
        count = 0
        prevIndex = 1000
        for job in self.jobs:
            filPosition = self.files[job.fileIndex].xPos
            if job.fileIndex != prevIndex:
                count = 0
                prevIndex = job.fileIndex
            if filPosition + count < height - 2:
                difCol = job.fileIndex % 2 + 2
                highLighted = self.pointer.get() if not self.subMenus else self.subMenus[0].prevPointer.get()
                col = 1 if job.fileIndex == highLighted else difCol
                if filPosition + count >= 3:
                    screenData.append([filPosition + count, cPos + 2, job.displayName, col])
                count += 1
            else:
                hJobs += 1
        if hFiles:
            screenData.append([height - 2, 3, ' [%s more] ' % (hFiles), 0])
        if hJobs:
            screenData.append([height - 2, cPos + 3, ' [%s more] ' % (hJobs), 0])
        return screenData


    def createFrame(self):
        """ Creates the data used for painting the frame """
        screenData = []
        height, width = self.screen.getmaxyx()
        cPos = (width - 1) / 2
        # horizontal lines
        screenData.append([0, 0, '╭' + '─' * (width - 2) + '╮', 0])
        screenData.append([2, 1, '─' * (width - 2), 0])
        screenData.append([height - 2, 0, '└' + '─' * (width - 2) + '╯', 0])
        # vertical lines
        for yPos in range(1, height - 2):
            screenData.append([yPos, 0, '│', 0])
            screenData.append([yPos, width - 1, '│', 0])
            screenData.append([yPos, cPos, '│', 0])
        # intersections
        screenData.append([0, cPos, '┬', 0])
        screenData.append([2, cPos, '┼', 0])
        screenData.append([height - 2, cPos, '┴', 0])
        screenData.append([2, 0, '├', 0])
        screenData.append([2, width - 1, '┤', 0])
        return screenData


    def drawSubMenu(self, obj):
        """ Creates the data used for painting a complete menu frame. """
        col = []
        for i in range(len(obj.menuItems)):
            col.append(2)
        widthArray = []
        for o in obj.menuItems:
            if type(o) == list:
                widthArray.append(len(o[0]) + len(o[1]) + 2)
            else:
                widthArray.append(len(o))
        width = max(widthArray) + 2
        height = len(obj.menuItems) + 2
        screenData = []
        # horizontal lines
        screenData.append([obj.y + 3,          obj.x, '╭' + '─' * width + '╮', 5])
        screenData.append([obj.y + height + 2, obj.x, '└' + '─' * width + '╯', 5])
        # vertical lines & text
        if obj.highlighted != None:
            col[obj.highlighted] = 1
        else:
            col[self.pointer.get()] = 1
        for nr, vl in enumerate(obj.menuItems):
            screenData.append([obj.y + nr + 4, obj.x, '│' +  ' ' * width + '│', 5])
            if type(vl) == list:
                screenData.append([obj.y + nr + 4, obj.x + 2, vl[0], col[nr]])
                screenData.append([obj.y + nr + 4, obj.x + width - len(vl[1]), vl[1], 3])
            else:
                screenData.append([obj.y + nr + 4, obj.x + 2, vl, col[nr]])
        return screenData


    def updateStatus(self, status = False):
        """ Always run by displayscreen, but can be run separately """
        screenData = []
        if not status:
            status = self.status
        height, width = self.screen.getmaxyx()
        yPos = height - 1
        screenData.append([yPos, 0, ' ' * (width - 1), 6])
        screenData.append([yPos, 0, 'Status: ', 6])
        screenData.append([yPos, 8, status, 6])
        return screenData


    def showVideo(self, video_path):
        """ previews the video and activates keyboard shortcuts instruction """
        devNull = open(os.devnull, 'w')
        if runExternal("ps -A | grep vlc") == '':
            subprocess.Popen(["/usr/bin/vlc-wrapper", video_path, '--play-and-exit', '--no-fullscreen'], stdin=devNull, stdout=devNull, stderr=devNull, shell=False)
            self.status = 'VLC started'
        else:
            self.status = 'VLC is already running!'
        print self.status


    def drawInstructions(self, x, y):
        """ previews the video and activates keyboard shortcuts instruction """
        screenData = []
        screenData.append([y + 7,  x, '╭── VLC Controls ───────────────────╮', 5])
        screenData.append([y + 8,  x, '│ Pause                     <Space> │', 5])
        screenData.append([y + 9,  x, '│ Faster                        <+> │', 5])
        screenData.append([y + 10, x, '│ Slower                        <-> │', 5])
        screenData.append([y + 11, x, '│ 10 sek backwards     <ALT + LEFT> │', 5])
        screenData.append([y + 12, x, '│ 10 sek forwards     <ALT + RIGHT> │', 5])
        screenData.append([y + 13, x, '│ 1 min backwards     <CTRL + LEFT> │', 5])
        screenData.append([y + 14, x, '│ 1 min forwards     <CTRL + RIGHT> │', 5])
        screenData.append([y + 15, x, '└───────────────────────────────────╯', 5])
        return screenData


    def getCurrentFile(self):
        """ Returns currently selected file OBJECT """
        fileNo = self.pointer.get() if not self.subMenus else self.subMenus[0].prevPointer.get()
        fileObject = self.files[fileNo]
        return fileObject


    def getCurrentMenuItems(self):
        """ Returns all items hold by currently selected menu """
        items = []
        for r in self.subMenus[-1].menuItems:
            if type(r) == list:
                items.append(r[1])
        while len(items) < 3:
            items.append(None)
        return items


    def addJob(self, jobTypeID):
        """ Adds a job to the joblist, closes menu """
        flagJobBad, flagFileHasJob = False, False
        objFile = self.getCurrentFile()
        file, ext = os.path.splitext(objFile.name)
        # check packages
        if jobTypeID == 1 and not instPackages.ccextractor:
            self.status = "Cannot add job of this time, since the program 'ccextractor' was not found"
            return False
        if jobTypeID == 3 and not instPackages.mkvmerge:
            self.status = "Cannot add job of this time, since the program 'mkvmerge' was not found"
            return False
        if jobTypeID == 4 and not instPackages.handbrake:
            self.status = "Cannot add job of this time, since the program 'HandBrakeCLI' was not found"
            return False
        if ext.upper() == '.SRT' and jobTypeID != 2:
            self.status = "Invalid operation for this filetype!"
            return False
        for j in self.jobs:
            if j.fileIndex == objFile.no:
                flagFileHasJob = True
                if jobTypeID == j.operation:
                    flagJobBad = True
        if flagJobBad:
            self.status = "Not added, already in job-list!"
            return False
        # move files down, if more than one job
        if flagFileHasJob:
            self.moveFiles(1 + objFile.no)
        arg1, arg2, arg3 = self.getCurrentMenuItems()
        if jobTypeID == 1:      # extract
            newJob = Job(objFile.no, jobTypeID, arg1)
            self.tools.logEntry(1, 'Added job for "%s": Extract ttpage %s' % (objFile.name, arg1))
        elif jobTypeID == 2:    # shift cc
            newJob = Job(objFile.no, jobTypeID, arg1, arg2, arg3)
            self.tools.logEntry(1, 'Added job for "%s": Shift Closed Captions %s (%s)' % (objFile.name, arg1, arg2))
        elif  jobTypeID == 3:   # slice

            time1 = datetime.timedelta(hours=float(arg1[:2]), minutes=float(arg1[3:5]), seconds=float(arg1[6:8]))
            time2 = datetime.timedelta(hours=float(arg2[:2]), minutes=float(arg2[3:5]), seconds=float(arg2[6:8]))
            if time1 > time2:
                self.status = 'Cannot slice from greater time to smaller'
                return False
            else:
                newJob = Job(objFile.no, jobTypeID, arg1, arg2)
                self.tools.logEntry(1, 'Added job for "%s": Slice: (%s --> %s)' % (objFile.name, arg1, arg2))
        elif  jobTypeID == 4:   # mux
            newJob = Job(objFile.no, jobTypeID)
            self.tools.logEntry(1, 'Added job for "%s": Mux file' % (objFile.name))
        self.jobs.append(newJob)
        # sort list
        self.jobs = sorted(self.jobs, key=lambda x: (x.fileIndex, x.operation))
        # reset menus
        for r in range(len(self.subMenus)):
            self.remSubMenu()
        return 1


    def addSubMenu(self, ID, x, y, itemsList):
        """ Adds an item to the chain of submenus """
        if self.subMenus:
            self.subMenus[-1].highlighted = self.pointer.get()
        self.subMenus.append(SubMenu(ID, x, y, itemsList, self.pointer ))
        self.pointer = RangeIterator( len(itemsList) - 1 )


    def remSubMenu(self):
        """ Removes an item from the chain of submenus """
        if self.subMenus:
            popped = self.subMenus.pop()
            self.pointer = popped.prevPointer
            if self.subMenus:
                self.subMenus[-1].highlighted = None


    def getActiveMenuID(self):
        if self.subMenus:
            return self.subMenus[-1].ID
        else:
            return 0


    def getInput(self):
        """ Retrieve input from the keyboard and proccess those"""
        height, width = self.screen.getmaxyx()
        keyPressed = self.screen.getch()
        mID = self.getActiveMenuID()    # menu
        itemNo = self.pointer.get()     # item
        selectedFile = self.getCurrentFile()
        if self.subMenus:
            x = self.subMenus[-1].x
            y = self.subMenus[-1].y
        if keyPressed == curses.KEY_UP:
            if not self.subMenus and selectedFile.xPos < 7 and itemNo > 3:
                self.moveFiles(0, False)
            self.pointer.dec()
            self.status = 'OK'
        if keyPressed == curses.KEY_DOWN:
            if not self.subMenus and selectedFile.xPos > (height - 11) and itemNo < (len(self.files) - 1):
                self.moveFiles(0, True)
            self.pointer.inc()
            self.status = 'OK'
        if keyPressed == curses.KEY_RIGHT or keyPressed == curses.KEY_ENTER or keyPressed == 10 or keyPressed == 13:
            if mID == 10:
                self.tools.processJobs()
            elif mID == 0:
                maxLength = ((self.screen.getmaxyx()[1] - 1) / 2) - 1
                yPos = (len(selectedFile.name) + 3) if len(selectedFile.name) < maxLength else maxLength
                self.addSubMenu( 1, yPos, selectedFile.xPos - 3, ['Slice', 'Compress', 'Extract CC', 'Shift CC', 'Remove Jobs', 'Forget'] )
            elif mID == 1:
                if itemNo == 0:
                    self.addSubMenu( 2, x + 14, y + 1, [['Start:','00:00:00'], ['End:', '00:00:00'], 'Preview', '<Add Job>'] )
                elif itemNo == 1:
                    self.addSubMenu( 3, x + 14, y + 2, ['<Add Job>'] )
                elif itemNo == 2:
                    self.addSubMenu( 4, x + 14, y + 3, [['Teletext page:','398'],'<Add Job>'] )
                elif itemNo == 3:
                    defShift = '00:00:00'
                    defMax   = '00:00:00'
                    # find values from slice, if any
                    for j in self.jobs:
                        if j.fileIndex == self.subMenus[0].y and j.operation == 3:
                            t1 = j.argument1
                            t2 = j.argument2
                            time1 = datetime.timedelta(hours=float(t1[:2]), minutes=float(t1[3:5]), seconds=float(t1[6:8]))
                            time2 = datetime.timedelta(hours=float(t2[:2]), minutes=float(t2[3:5]), seconds=float(t2[6:8]))
                            defShift = j.argument1
                            defMax   = str(time2 - time1)
                            if len(defMax) == 7:
                                defMax = '0' + defMax





                            self.tools.logEntry(4, "jobs: " + str(self.jobs))
                            self.tools.logEntry(4, "j.fileIndex: " + str(j.fileIndex))
                            self.tools.logEntry(4, "self.subMenus[0].y: " + str(self.subMenus[0].y))
                            self.tools.logEntry(4, "j.operation: " + str(j.operation))
                            self.tools.logEntry(4, "j.fileIndex == self.subMenus[0].y: " + str(j.fileIndex == self.subMenus[0].y))
                            self.tools.logEntry(4, "j.operation == 3: " + str(j.operation == 3))




# Her et sted bliver defMax og defShift glemt

# 2017-05-21|19:32:47 INFO MovieTools.py started
# 2017-05-21|19:32:51 INFO Added job for "Mars.3.en.mkv": Slice: (10:00:00 --> 20:00:00)
# 2017-05-21|19:32:53 CRITICAL jobs: [<__main__.Job instance at 0x7fa621a55fc8>]
# 2017-05-21|19:32:53 CRITICAL j.fileIndex: 0
# 2017-05-21|19:32:53 CRITICAL self.subMenus[0].y: 0
# 2017-05-21|19:32:53 CRITICAL j.operation: 3
# 2017-05-21|19:32:53 CRITICAL j.fileIndex == self.subMenus[0].y: True
# 2017-05-21|19:32:53 CRITICAL j.operation == 3: True
# 2017-05-21|19:32:54 INFO Added job for "Mars.3.en.mkv": Shift Closed Captions 10:00:00 (10:00:00)
# 2017-05-21|19:33:00 INFO Added job for "Mars.4.en.mkv": Slice: (30:00:00 --> 40:00:00)
# 2017-05-21|19:33:03 INFO Added job for "Mars.4.en.mkv": Shift Closed Captions 00:00:00 (00:00:00)
# 2017-05-21|19:33:06 INFO Program terminated by user




                    self.addSubMenu( 5, x + 14, y + 4, [['Shift:', defShift], ['Max:', defMax], ['Negative:', 'True'], '<Add Job>'] )
                elif itemNo == 4:
                    self.addSubMenu( 6, x + 14, y + 5, ['<Remove>'] )
                elif itemNo == 5:
                    self.addSubMenu( 7, x + 14, y + 6, ['<Forget>'] )
            elif mID == 2:
                if itemNo == 0 or itemNo == 1:
                    currentTime = self.subMenus[-1].menuItems[itemNo][1]
                    editedTime = self.tools.timeEdit(currentTime, x, y + itemNo)
                    self.subMenus[-1].menuItems[itemNo][1] = editedTime
                elif itemNo == 2:                                                       # ShowPreview
                    if not instPackages.vlc:
                        self.status = "Cannot preview video, since the program 'vlc' was not found"
                    else:
                        self.displayInstr = True
                        self.showVideo(selectedFile.name)
                elif itemNo == 3:
                    self.displayInstr = False
                    self.addJob(3)                                                       # slice
            elif mID == 3:
                self.addJob(4)                                                           # compress
            elif mID == 4:
                if itemNo == 0:                                                          # extract cc
                    currentPage = self.subMenus[-1].menuItems[itemNo][1]
                    editedPage = self.tools.timeEdit(currentPage, x + 8, y + itemNo)
                    self.subMenus[-1].menuItems[itemNo][1] = editedPage
                elif itemNo == 1:
                    self.addJob(1)
            elif mID == 5:
                if itemNo == 0 or itemNo == 1:                                           # shift cc
                    currentTime = self.subMenus[-1].menuItems[itemNo][1]
                    editedTime = self.tools.timeEdit(currentTime, x, y + itemNo)
                    self.subMenus[-1].menuItems[itemNo][1] = editedTime
                elif itemNo == 2:
                    currentValue = self.subMenus[-1].menuItems[itemNo][1]
                    value = self.tools.boolEdit(currentValue, x + 3, y + itemNo)
                    self.subMenus[-1].menuItems[itemNo][1] = value
                elif itemNo == 3:
                    self.addJob(2)
            elif mID == 6:
                fileID = self.subMenus[0].y
                # restore lines
                for no, j in enumerate(self.jobs):
                    if j.fileIndex == fileID:
                        if no > 0:
                            self.moveFiles(1 + j.fileIndex, True)
                self.jobs = [j for j in self.jobs if j.fileIndex != fileID]
                self.status = 'All jobs for selected file removed'
                self.tools.logEntry(1, 'All jobs for "%s" removed' % (self.files[fileID].name))
                # reset menus
                for r in range(len(self.subMenus)):
                    self.remSubMenu()
            elif mID == 7:
                fileID = self.subMenus[0].y
                for j in self.jobs:
                    if j.fileIndex == fileID:
                        self.status = 'Cannot remove file with jobs pending'
                        return 0
                flag = False
                for no, f in enumerate(self.files):
                    if f.no == fileID:
                        flag = True
                        self.files.remove(f)
                    if flag:
                        self.files[no].xPos -= 1
                        self.files[no].no -= 1
                self.status = 'Forgot about "%s"' % (self.files[fileID].name)
                self.tools.logEntry(1, 'Forgot about "%s"' % (self.files[fileID].name))
                # reset menus
                for r in range(len(self.subMenus)):
                    self.remSubMenu()
                self.pointer = RangeIterator(len(self.files) - 1, False)
        if keyPressed == curses.KEY_LEFT:
            self.displayInstr = False
            self.remSubMenu()
        if keyPressed == 32:     # Keypress 'space' = Main Menu
            if self.subMenus and self.subMenus[-1].ID  == 10:
                self.pointer = self.subMenus[-1].prevPointer
                self.subMenus.pop()
            else:
                # Calculate center
                wHeight, wWidth = self.screen.getmaxyx()
                xCord = (wWidth / 2 - 6)
                yCord = (wHeight / 2 - 9)
                self.addSubMenu(10, xCord, yCord, ['Execute'])
        if keyPressed == 113:     # Keypress 'q' or ESC = End Application
            self.running = False


    def compareItemsUNUSED(self):
        """ Shows the content of two files """
        running = True
        focus = [0, 0]
        maxLines = max(len(fileLinesOrig), len(fileLinesBack))
        while running:
            for line in range(self.parent.height - 5):
                nr = line + focus[1]
                leftText = fileLinesOrig[nr] if nr < len(fileLinesOrig) else ''
                self.parent.screen.addstr(3 + line, 1, leftText, curses.color_pair(0))
            # wait for and process
            self.parent.screen.refresh()
            keyPressed = self.parent.screen.getch()
            if keyPressed == curses.KEY_UP:
                if focus[1] > 0:
                    focus[1] -= 1
            elif keyPressed == curses.KEY_DOWN:
                if line + focus[1] < maxLines:
                    focus[1] += 1
            elif keyPressed == 113:     # Keypress 'q' = End Application
                running = False
        return 1


# --- Main Program -------------------------------------------------------------------------------

parser = argparse.ArgumentParser(formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=40))
parser.add_argument('files', type=str, nargs="*")
parser.add_argument("-s", "--shutdown",  action="store_true", dest='shutdown', help="Shuts don the computer when all jobs done")
parser.add_argument("-v", "--verbose",   action="store_true", dest='verbose',  help="Prints all output from external processes to screen")
parser.add_argument("-l", "--log",       action="store_true", dest='log',      help="Shows log and exits")
parser.add_argument("-o", "--outdir",    action="store",      dest='outdir',   help="All processed files will be moved to this directory when done", nargs=1)
args = parser.parse_args()

if args.outdir:
    if os.path.exists(args.outdir[0]):
        args.outdir = args.outdir[0]
    else:
        sys.exit("\n  Output directory does not exist! Exiting....\n")
if args.log and os.path.exists('/var/log/movieTools.log'):
    sys.exit(open('/var/log/movieTools.log', 'r').read())
if not args.files:
    sys.exit("\n  No files to work with. Cannot continue...\n")
else:
    for f in args.files:
        if not os.path.exists(f):
            sys.exit('\n  "%s" does not exist! Cannot continue...\n' % (f))
        else:
            file, ext = os.path.splitext(f)
            if not ext.upper() in acceptedFiles:
                sys.exit('\n  Cannot process file of type "%s"...\n' % (ext))
if args.shutdown and os.getuid() != 0:
    sys.exit("\n  Cannot run shutdown on exit, unless run as root user! Exiting....\n")
if not os.access('/var/log/movieTools.log', os.W_OK):
    raw_input("\n  /var/log/movieTools.log could not be accessed. Logging will be disabled. (Any key to continue)")

instPackages = Packages()
if checkPackage('handbrake-cli'):
    instPackages.handbrake = True
if checkPackage('mkvtoolnix'):
    instPackages.mkvmerge = True
if checkPackage('vlc'):
    instPackages.vlc = True
if runExternal('ccextractor') != '':
    instPackages.ccextractor = True

# clean up /tmp
for l in os.listdir('/tmp'):
    if l.endswith('.mkv') or l.endswith('.srt'):
        fromPath = os.path.join('/tmp/', l)
        file, ext = os.path.splitext(l)
        toPath = os.path.join('/tmp/', file + '_' + ext[1:] + '.tmp')
        shutil.move(fromPath, toPath)

# run program
pMT = MovieTools_View(args.files)


# --- TODO ---------------------------------------------------------------------------------------
# - 













