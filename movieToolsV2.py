#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import curses
import signal
import shutil
import locale
import shutil
import poktools
import argparse
import datetime
from ncengine import NCEngine

locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

version = "v2.01"   # Converting to Python3....

# --- Variables ----------------------------------------------------------------------------------

tempFiles = '/mnt/6tb_hdd/.temp'

acceptedFiles = ['.TS', '.MKV', '.SRT', '.MP4']

extJobs = {   1 : "ccextractor -o '%s' -tpage %s '%s'",     # (outputFile, textTV_page, inputFile)   # side 398
			  3 : "mkvmerge -o '%s' --split parts:%s-%s '%s'", # (outputfile, cut_from_time, cut_to_time, inputfile)
			  4 : "HandBrakeCLI -e x264  -q 23.0 -a 1 -E ffaac -B 160 -6 dpl2 -R Auto -D 0.0 --audio-copy-mask aac,ac3,dtshd,dts,mp3 \
					 --audio-fallback ffac3 -f mkv --loose-anamorphic --modulus 2 -m --x264-preset veryfast --h264-profile main \
					 --h264-level 4.0 -s '1' -o '%s' -i '%s'",     # (Inputfile, outputfile)
			4.1 : " --srt-file '%s' --srt-codeset UTF-8"
		  }

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
		print(self.nr)
		print(self.tidFra, '-->', self.tidTil)
		for l in self.textLinier:
			print(l)


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


class MovieTools:
	""" Carries out actions, requested by the user through the calling class """

	def __init__(self, files):
		# init view
		self.view = NCEngine()
		self.view.screenBorder = True
		self.view.addGridLine('v', 50.0)
		self.view.addGridLine('h', 2)
		# Add top menus
		self.view.addLabel(0, 0, 'Mediafiles:', 6)
		self.view.addLabel(50., 0, 'Jobs:', 6)
		self.view.status = 'MovieTools initiated...'


		menuID = self.view.addMenu(0, 2, [1,2,3,4,5], self.view.color['blue'], False)
		textBoxID = self.view.addTextbox(50., 2, ['Hello', 'fucker'], self.view.color['red'], False)
		self.view.activeObject = menuID


		self.logEntry(1, 'MovieTools.py started')
		self.loop()


	def loop(self):
		""" Ensure that view runs until terminated by user """
		while self.view.running:
			self.view.render()
			keyPressed = self.view.getInput()
		self.view.terminate()
		self.logEntry(1, 'Program terminated by user')
		sys.exit('\n Program terminated by user\n')


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


	def parseLogs():
		""" Finds and returns the last set of jobs """
		logText = open('/var/log/movieTools.log', 'r').read().split('\n')
		lineCount = len(logText) - 1
		jobs = []
		while 1:
			lineCount -= 1
			line = logText[lineCount]
			if line != '':
				if 'Added job' in line:
					tmp, info = line.split('Added job for ')
					film, info = info.split(':', 1)
					film = film.replace('"', '')
					if 'Extract' in info:
						tmp, ttpage = info.split('ttpage ')
						jobs.append([film, 1, ttpage])
					elif 'Shift Closed Captions' in info:
						tmp, info = info.split('Captions ')
						tid, direction = info.split(', direction: ')
						shift, cap = tid.split(' ')
						shift = shift.replace('(', '').replace(')', '') # remove extra paranthesis from loaded .log
						cap = cap.replace('(', '').replace(')', '')     # remove extra paranthesis from loaded .log
						jobs.append([film, 2, cap, shift, direction])
					elif 'Slice' in info:
						jobType, tid = info.split(':', 1)
						fra, til = tid[2:-1].split(' --> ')
						til = til.replace('(', '').replace(')', '')     # remove extra paranthesis from loaded .log
						fra = fra.replace('(', '').replace(')', '')     # remove extra paranthesis from loaded .log
						jobs.append([film, 3, fra, til])
					elif 'Mux' in info:
						jobs.append([film, 4])
					else:
						sys.exit('Failed to parse log-file')
			else:
				break
		jobs.reverse()
		return jobs


	def moveFile(self, scr, dst):
		# make sure source exists
		if os.path.exists(scr):
			os.chmod(scr, 0o777)
		else:
			self.logEntry(4, '\nSource File does not exist, cannot contine')
			self.parent.killScreen()
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


	def getFileOut(fileName, opr, newExt, newDir):
		""" Formats filename to be used as output. Optional jobType Description is added to name """
		path, fil = os.path.split(fileName)
		name, ext = fil.rsplit('.', 1)
		operation = opr if opr else ''
		outPath = newDir if newDir else path
		extension = newExt if newExt else ext
		return os.path.join(outPath, name) + operation + '.' + extension


	def processJobs(self):
		""" Process list of jobs, one by one """
		previous = 100
		jobList = self.parent.jobs
		height, width = self.parent.screen.getmaxyx()
		self.screen.clear()
		self.wts(1, 0, 'Processing ' + str(len(jobList)) + ' batch job' + ('s' if len(jobList) > 1 else '') + '....', 0)
		out, lineOut, lineNr = '', '', 1
		for jobNr, job in enumerate(jobList):
			if lineNr >= height - 5:
				lineNr = 3
			oFile = self.parent.files[job.fileIndex]
			fileIn = os.path.join(oFile.path, oFile.name)
			# check/reset stack
			if job.fileIndex != previous:
				previous = job.fileIndex
				stack = {'srt' : None, 'cmp' : None, 'cut' : None, 'cut_from' : None}
			# determine job type
			if job.operation == 1:
				srt_file = self.getFileOut(fileIn, None, 'srt', tempFiles)
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
					self.wts(2 + lineNr, 0, '------ Running job ' + str(jobNr + 1) + ' of ' + str(len(self.parent.jobs)) + ': (Shift) ------------------')
					oHS = HandleSubtitles(fileToMove, job.argument1, job.argument2, job.argument3)
					direction = '-->' if job.argument3.startswith('True') else '<--'
					self.wts(3 + lineNr, 0, 'CC shifted %s (%s), capped at %s' % (job.argument1, direction, job.argument2))
					self.wts(4 + lineNr, 0, '------ Job ' +  str(jobNr + 1) + ' done! ' + '-----------------------------------')
					self.logEntry(1, 'Finished processing job ' + str(jobNr + 1))
					lineNr += 4
			if job.operation == 3:
				cut_file = self.getFileOut(fileIn, '_cut', 'mkv', tempFiles)
				cmdLine = extJobs[3] % (cut_file, job.argument1, job.argument2, fileIn)
				stack['cut'] = cut_file
			if job.operation == 4:		# compress
				fil = stack['cut'] if stack['cut'] else fileIn
				cmp_file = self.getFileOut(fil, '_cmp', 'mkv', tempFiles)
				cmdLine = extJobs[4] % (cmp_file, fil)
				stack['cmp'] = cmp_file
				srt_file = fileIn[:-3] + 'srt'	# hack!
				if os.path.exists(srt_file):
					cmdLine += extJobs[4.1] % (srt_file)
				elif stack['srt']:		# Should be the same?
					cmdLine += extJobs[4.1] % (stack['srt'])
			self.logEntry(1, 'CMD: ' + str(cmdLine))
			if cmdLine:
				process = subprocess.Popen(cmdLine, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
				self.logEntry(1, 'Started processing job ' + str(jobNr + 1))
				self.wts(2 + lineNr, 0, '------ Running job ' + str(jobNr + 1) + ' of ' + str(len(self.parent.jobs)) + ': (' + job.displayName.split()[0] + ') ------------------', 0)
				while not (out == '' and process.poll() != None):
					out = process.stdout.read(1)
					if out == '\n':
						if args.verbose:
							self.wts(3 + lineNr, 1, '  ' + lineOut + '  ')
							lineNr += 1
						lineOut = ''
					elif out == '%':
						lineOut += '%  '
						self.wts(3 + lineNr, 1, '  ' + lineOut + '  ')
						lineOut = ''
					else:
						lineOut += out
				self.wts(4 + lineNr, 0, '------ Job ' +  str(jobNr + 1) + ' done! ' + '-----------------------------------')
				self.logEntry(1, 'Finished processing job ' + str(jobNr + 1))
				lineNr += 4
			if (jobNr + 1) == len(jobList) or job.fileIndex != jobList[jobNr + 1].fileIndex:
				self.wts(2 + lineNr, 0, '  All jobs processed for "' + oFile.name + '", doing cleanup......')
				lineNr += 4
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
					self.moveFile(finalFile, self.getFileOut(fileIn, ending, extension, outDir))
				self.wts(lineNr + 4, 10, 'Cleanup complete, processed file moved to "%s"' % (outDir))
				lineNr += 4
		if args.shutdown:
			runExternal("sudo init 0")
		else:
			self.wts(4 + lineNr, 0, '  All files processed, press any key to end program')
			self.screen.getch()
			self.parent.killScreen()
			self.logEntry(1, str(len(jobList)) + ' jobs processed successfully')
			self.logEntry(1, 'Program terminated normally')
			sys.exit('\n' + str(len(jobList)) + ' jobs processed, terminating normally\n')



# --- Main Program -------------------------------------------------------------------------------

parser = argparse.ArgumentParser(formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=40))
parser.add_argument('files', type=str, nargs="*")
parser.add_argument("-s", "--shutdown",  action="store_true", dest='shutdown', help="Shuts don the computer when all jobs done")
parser.add_argument("-v", "--verbose",   action="store_true", dest='verbose',  help="Prints all output from external processes to screen")
parser.add_argument("-l", "--log",       action="store_true", dest='log',      help="Shows log and exits")
parser.add_argument("-r", "--reload",    action="store_true", dest='reload',   help="Reload last entry in logs")
parser.add_argument("-o", "--outdir",    action="store",      dest='outdir',   help="All processed files will be moved to this directory when done", nargs=1)
args = parser.parse_args()

if args.outdir:
	if os.path.exists(args.outdir[0]):
		args.outdir = args.outdir[0]
	else:
		sys.exit("\n  Output directory does not exist! Exiting....\n")
if args.log and os.path.exists('/var/log/movieTools.log'):
	sys.exit(open('/var/log/movieTools.log', 'r').read())
if args.reload and os.path.exists('/var/log/movieTools.log'):
	reloadedJobs = parseLogs()
	files = []
	for j in reloadedJobs:
		if os.path.exists(j[0]) and j[0] not in args.files:
			args.files.append(j[0])
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

#check needed packages
#poktools.ensurePackage('handbrake-cli')
#poktools.ensurePackage('mkvtoolnix')
#poktools.ensurePackage('vlc')
#if poktools.runExternal('ccextractor') != '':
#	poktools.installPackage('ccextractor')

# clean up tempFiles
for l in os.listdir(tempFiles):
	if l.endswith('.mkv') or l.endswith('.srt'):
		fromPath = os.path.join(tempFiles, l)
		file, ext = os.path.splitext(l)
		toPath = os.path.join(tempFiles, file + '_' + ext[1:] + '.tmp')
		shutil.move(fromPath, toPath)

# run program
pMT = MovieTools(args.files)


# --- TODO ---------------------------------------------------------------------------------------
# - Posibility to mux EXTERNAL .srt into file
# - Remove single job from job list (or edit?)










