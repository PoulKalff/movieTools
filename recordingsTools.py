#!/usr/bin/env python3

import os
import cv2
import sys
import json
import shutil
import argparse
import datetime
import subprocess
from pymediainfo import MediaInfo

# --- Variables ----------------------------------------------------------------------------------

cutout = ''
filePermissions = '755'
validFormats = ['.ts','.mkv','.mp4','.avi']
htsLogFiles = '/home/hts/.hts/tvheadend/dvr/log/'
extPrograms =	{
			'ccextractor' : 'apt install -y ccextractor\n',
			'HandBrakeCLI': 'apt install -y handbrake-cli',
			'pymediainfo' :	'sudo apt-get install -y libmediainfo-dev'
		}
extJobs = 		{		1    : "ccextractor -o '%s' -tpage %s '%s'",     # (outputFile, textTV_page, inputFile)
					2    : "HandBrakeCLI -e x264  -q 23.0 --loose-anamorphic --x264-preset veryfast --h264-profile main --h264-level 4.0%s -o '%s' -i '%s' %s",     # (Srt-file, Outputfile, Inputfile)
					2.1  : " --srt-default --srt-codeset UTF-8",
					2.11 : " --subtitle %s --srt-file '%s' --srt-lang '%s'",
					2.2  : "--start-at duration:%d --stop-at duration:%d",
#					3    : "ffmpeg -i '%s' -i '%s' -map 0 -map 1 -c copy -metadata:s:s:0 language=eng -disposition:s:0 default '%s'",	# (Inputfile, Srt-file, Outputfile)
					3    : "ffmpeg -i '%s'%s -map 0%s -c copy%s -disposition:s:0 default '%s'",	# (Inputfile, 3.1, 3.2, 3.3, Outputfile)
					3.1  : " -i '%s'",
					3.2  : " -map %s",
					3.3  : " -metadata:s:s:%s language=%s",
					4    : "ffmpeg -i '%s' -f srt -i '%s' -c:v libx264 -preset ultrafast -crf 30 -map 0:0 -map 0:1 -map 1:0 -c:a copy -c:s srt '%s'"     # (Inputfile, Srt-file, Outputfile) NOT USED

				}
serviceList =	{
					'DR1'		: 888,
					'DR2'		: 888,
					'TV 2 DANMARK'	: 399,
					'TV 2 CHARLIE'	: 398,
				}

# --- Classes ------------------------------------------------------------------------------------

class fileClass:
	""" Object to hold all information about the file being processed (or any file) """

	ext = None
	path = None
	noExt = None
	fileName = None
	fullPath = None
	outFile = None
	subLang = None
	service = None

	def __init__(self, fn):
		self.fullPath = os.path.abspath(fn)
		self.path, self.fileName = os.path.split(self.fullPath)
		self.noExt, self.ext = os.path.splitext(self.fileName)
		self.outFile = self.noExt + '.mkv' if self.ext != '.mkv' else self.noExt + '.new.mkv'
		if True:
			self.outFile = self.outFile.replace(' ', '.')
		self.srtFiles = []

	def checkSrt(self):
		for f in os.listdir(self.path):
			filename, ext = os.path.splitext(f)
			if f.startswith(self.noExt) and ext == '.srt':
				language = f[-6:-4] if f[-4] == '.' and f[-7] == '.' else '<unknown>'
				if args.forceLanguage != None:
					language = args.forceLanguage[0]
				self.srtFiles.append([f, language])


# --- Defs ---------------------------------------------------------------------------------------


def secondsToTime(secondsIn):
	hours, minutes = 0, 0
	minutes, seconds= divmod(secondsIn, 60)
	hours, minutes = divmod(minutes, 60)
	hours =   '0' + str(hours) if hours < 10 else str(hours)
	minutes = '0' + str(minutes) if minutes < 10 else str(minutes)
	seconds = '0' + str(seconds) if seconds < 10 else str(seconds)
	return hours + ':' + minutes + ':' + seconds


def timeToSeconds(timeIn):
	splitup = timeIn.split(':')
	if len(splitup) == 3:
		return int(splitup[0]) * 3600  + int(splitup[1]) * 60 + int(splitup[2])
	elif len(splitup) == 2:
		return int(splitup[0]) * 60 + int(splitup[1])
	elif len(splitup) == 1:
		return int(splitup[0])


def calculateCutting(_from, _to):
	""" calculates times to cut FROM (in seconds) and TO (which is actually duration from start) """
	_fromOut = timeToSeconds(_from)
	_toOut = timeToSeconds(_to) - _fromOut	# because to must be DURATION
	return (_fromOut, _toOut)


def runProcess(cmd):
	process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
	lineOut = ''; out = ''
	while not (out == '' and process.poll() != None):
		out = process.stdout.read(1)
		if out == '\n':
			lineOut = ''
		elif out == '%':
			lineOut += '%'
			print('    ' + lineOut + '                                                  \r', sep=' ', end='', flush=True)
			lineOut = ''
		else:
			lineOut += out


# --- Main ---------------------------------------------------------------------------------------

#check parameters
if os.getuid() != 0:
	sys.exit('\n  Must be run with admin priviliges\n')
if sys.version_info.major < 3:
	sys.exit('\n  Must use Python3 to execute this script\n')

#check arguments
parser = argparse.ArgumentParser(formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=120))
parser.add_argument('files', type=str, nargs="*")
parser.add_argument("-e", "--extractSubtitles",	action="store_true",	help="Extracts subtitles before encode, and includes these in mux")
parser.add_argument("-s", "--showCommand",	action="store_true",	help="Prints the command to be executed and exits")
parser.add_argument("-d", "--delete",		action="store_true",	help="Deletes all files after any operation")
parser.add_argument("-u", "--updateDVR",	action="store_true",	help="Update tvheadend-files to use .MKV-files")
parser.add_argument("-c", "--cutout",		action="store",		help="Only encode from and to specific timemarks ('hh:mm:ss,hh:mm:ss')", type=str, nargs=1)
parser.add_argument("-n", "--noCheckMedia",	action="store_true",	help="Do not check file info")
parser.add_argument("-p", "--noSetPermissions",	action="store_true",	help="Do not change file permissions")
parser.add_argument("-i", "--noCheckExt",	action="store_true",	help="Does not check that external programs exist")
parser.add_argument("-m", "--mux",		action="store_true",	help="Encodes file to according to presets (mkv)")
parser.add_argument("-k", "--copy",		action="store_true",	help="Join files into mkv-container (copy)")
parser.add_argument("-f", "--forceLanguage",	action="store",		help="Force encoded file to set subtitle language to <FORCELANGUAGE>", type=str, nargs=1),
parser.add_argument("-q", "--findStopEnd",	action="store_true",	help="Find timemarks for cutout, based on frame recognition")
args = parser.parse_args()

# adjust arguments selected				<------------- Probably better to inform user that switches a mutualy exclusive
if args.showCommand: args.noCheckMedia = True
if args.extractSubtitles: args.noCheckMedia = False
if (len(sys.argv) < 2 or not os.path.exists(sys.argv[1])) and not args.updateDVR:
	sys.exit('\n  Must get existing file as first argument\n')
for f in  args.files:
	if not os.path.splitext(f)[1] in validFormats:
		args.files.pop( args.files.index(f) )
		print('    File "' + f + '" was removed from selected files because of invalid extension')

#check for existence of dvr/log-files, and update them if so
if args.updateDVR:
	print('\n  Checking TVHeadend logfiles...')
	files = os.listdir(htsLogFiles)
	for f in files:
		print('    Looking at "' + f + '"' )
		with open(os.path.join(htsLogFiles, f)) as fh:
			data = json.load(fh)
			fh.close()
			try:
				mediaFile = data['files'][0]['filename']
			except:
				mediaFile = False
			if mediaFile:
				print('\tMediafile referenced is "' + mediaFile + '"' )
				if os.path.exists(os.path.join(htsLogFiles, mediaFile)):
					print('\t\tFile exists')
				else:
					print('\t\tFile does not exist')
					noExt, ext = os.path.splitext(mediaFile)
					if os.path.exists(os.path.join(htsLogFiles, noExt + '.mkv')):
						print('                mkv-file exists, updating reference...', end='')
						# update data & save file
						data['files'][0]['filename'] = os.path.join(htsLogFiles, noExt + '.mkv')
						with open(os.path.join(htsLogFiles, f), 'w') as fh:
							json.dump(data, fh, indent=4)
							fh.close()
						print('Done!')
					else:
						print('                mkv-file does not exist, file deleted')
						os.remove(os.path.join(htsLogFiles, f))
			else:
				print('            No mediafile is referenced, file deleted')
				os.remove( os.path.join(htsLogFiles, f) )
	print('\n  Files fixed. Should tvheadend be restarted? (y/n) : ', end='')
	reply = input()
	if reply == 'y':
		print('    Restarting.....', end='')
		runProcess('sudo systemctl restart tvheadend.service')
		print('Done')
	else:
		print('    No restart requested')
	sys.exit('\n  All done!\n')

#check external programs
allCorrect = True
if not args.noCheckExt:
	print('\n  Checking for external programs...')
	for prog in extPrograms:
		print('    ' + prog + '...', end='')
		if subprocess.call(['which', prog], stdout=subprocess.PIPE):
			print(' does not seem to be installed. Install with "' + extPrograms[prog] + '"\n')
			allCorrect = False
		else:
			print(' OK')
	try:
		from pymediainfo import MediaInfo
		print('    pymediainfo... OK')
	except:
		print('    pymediainfo... does not seem to be installed. Install with "pip3 install pymediainfo"\n')
		allCorrect = False
	if not allCorrect:
		sys.exit('  Some external programs were mising, exiting...\n')

# creating fileObject(s)
fileHandles = []
for f in args.files:
	fh = fileClass(f)
	fh.checkSrt()
	if not args.noCheckMedia:
		print('\n  Collecting media-info from "' + fh.fileName + '":')
		mediaInfo = {}
		fileInfo = json.loads(MediaInfo.parse(fh.fullPath).to_json())
		for track in fileInfo['tracks']:
			mediaInfo[track['track_type']] = track
		# cherrypick info
		fh.subLang = mediaInfo['Other']['language']	if 'Other' in mediaInfo else False
		fh.service = mediaInfo['Menu']['service_name'] if 'Menu' in mediaInfo else False

	# show collected data
	srtLength = 0 if fh.srtFiles == [] else len(fh.srtFiles[0][0]) + len(fh.srtFiles[0][1]) + 3
	maxLength = max(len(fh.fileName), srtLength, len(fh.outFile))
	print('\n    +' + ('-' * (maxLength + 21)) + '+')
	print('    | File             : ' + fh.fileName, ((maxLength - len(fh.fileName)) * ' ') + '|')
	if not fh.srtFiles:
		print('    | Subtitle file(s) : <none>', ((maxLength - 6) * ' ') + '|')
	else:
		print('    | Subtitle file(s) : ' + fh.srtFiles[0][0], '(' + fh.srtFiles[0][1] + ')', ((maxLength - srtLength) * ' ') + '|')
	for sf in fh.srtFiles[1:]:
		print('    |                    ' + sf[0], '(' + sf[1] + ')', ((maxLength - srtLength) * ' ') + '|')
	print('    | MKV file         : ' + fh.outFile,  ((maxLength - len(fh.outFile)) * ' ') + '|')
	if fh.subLang:
		print('    | Service          : ' + fh.service,  ((maxLength - len(fh.service)) * ' ') + '|')
	if fh.subLang:
		print('    | Language         : ' + fh.subLang,  ((maxLength - len(fh.subLang)) * ' ') + '|')
	print('    +' + ('-' * (maxLength + 21)) + '+')
	cmdLineSrt = False
	if args.findStopEnd: #		Tester med:	13:08,1:02:24
		if os.path.exists("refImageFROM.jpg") and os.path.exists("refImageTO.jpg"):
			print("\n  Both reference images exist, searching...\n")












			sys.exit("\n  nonImplmented exception: findStopEnd\n")
		else:
			print("\n  Reference images do not exist\n")
			raw = input('\n    Type start and end frames ("hh:mm:ss,hh:mm:ss") : ')
			# parse string given
			if ',' in raw:
				fra, til = raw.split(',')
				fraSeconds = timeToSeconds(fra)
				tilSeconds = timeToSeconds(til)
			else:
				sys.exit('\nMalformed cutout string: must contain two timemarks, seperated by "," ( e.g. "hh:mm:ss,hh:mm:ss")\n')
			# extract two reference images and then end program
			cap = cv2.VideoCapture(args.files[0])			# Open the video file
			fps = cap.get(cv2.CAP_PROP_FPS)				# Get the frames per second
			frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)		# Get the total numer of frames in the video.
			fraFrame = int(fraSeconds * fps)
			tilFrame = int(tilSeconds * fps)
			# save first frame
			cap.set(cv2.CAP_PROP_POS_FRAMES, fraFrame)
			ret, frame = cap.read()
			cv2.imwrite(f"refImageFROM.jpg", frame)
			# save second frame
			cap.set(cv2.CAP_PROP_POS_FRAMES, tilFrame)
			ret, frame = cap.read()
			cv2.imwrite(f"refImageTO.jpg", frame)
			# cleanup and end
			os.chmod("refImageFROM.jpg", 0o777)
			os.chmod("refImageTO.jpg", 0o777)
			cap.release()
			cv2.destroyAllWindows()
			print(cap, fps, frame_count)
			sys.exit("Reference frames were crated without error")
	elif args.extractSubtitles:
		if not fh.service:
			sys.exit('\n  No service info found in file, exiting... Please extract .srt manually\n')
		cmdLineSrt = extJobs[1] % (fh.noExt + '.srt', serviceList[fh.service.upper()], fh.fileName)
		if args.showCommand:
			print('\n  Extraction-command to be executed: ' + cmdLineSrt + '\n')
			sys.exit()
		else:
			print('\n  Extracting subtitles from "' + fh.fileName + '":')
			runProcess(cmdLineSrt)
			print('    Subtitle extracted');
			fh.checkSrt()

	# move time in subtitles and slice file, if requested
	if args.cutout:
		raw = args.cutout[0]
		# parse string given
		if ',' in raw:
			fra, til = raw.split(',')
		else:
			sys.exit('\nMalformed cutout string: must contain two timemarks, seperated by "," ( e.g. "hh:mm:ss,hh:mm:ss")\n')
		cutout = extJobs[2.2] % calculateCutting(fra, til)
	if args.mux:
		# calculate argument
		srtArg = extJobs[2.1] if fh.srtFiles else ''
		for count, f in enumerate(fh.srtFiles):
			srtArg += extJobs[2.11] % (count, f[0], f[1])
		cmdLine = extJobs[2] % (srtArg, fh.outFile, fh.fileName, cutout)
		if args.showCommand:
			if cmdLineSrt:
				print('\n  Extraction-command to be executed: ' + cmdLineSrt)
			print('  Compresion-command to be executed: ' + cmdLine)
			print('\n  All done!\n')
			sys.exit()
		else:
			print('\n  Encoding to"' + fh.fileName + '":')
			runProcess(cmdLine)
	elif args.copy:
		srtArg = ['', '', '']
		for nr, f in enumerate(fh.srtFiles):
			srtArg[0] += extJobs[3.1] % f[0]
			srtArg[1] += extJobs[3.2] % (nr + 1)
			srtArg[2] += extJobs[3.3] % (nr, f[1])
		cmdLine = extJobs[3] % (fh.fileName, srtArg[0], srtArg[1], srtArg[2], fh.outFile)
		if args.showCommand:
			if cmdLineSrt:
				print('\n  Extraction-command to be executed: ' + cmdLineSrt)
			print('  Compresion-command to be executed: ' + cmdLine)
			print('\n  All done!\n')
			sys.exit()
		else:
			print('\n  Copying streams from "' + fh.fileName + '":')
			runProcess(cmdLine)

	if os.path.exists(fh.outFile) and not args.noSetPermissions:
		print('\n  Setting permissions to encoded file(' + filePermissions + ')...', end='')
		os.chmod(fh.outFile, int(filePermissions, 8))
		print('Done!')
	# deleting used files, if requested
	if os.path.exists(fh.outFile) and args.delete:
		print('\n  Removing original files...')
		os.remove(fh.fileName)
		print('    ' + fh.fileName + '...Done!')
		for f in fh.srtFiles:
			os.remove(f[0])
			print('    ' + f[0] + '...Done!')

print('\n  All done!\n')



# --- Notes ---------------------------------------------------------------------------------------
#	- intet output fra ffmpeg  ved copy
#	- mv .new.mkv --> .mkv after successfull operation
#	- chmod subtitles after extraction
#	- option to shutdown after completion
#	- valider .srt-fil og ignorere hvis len() == 3
#	- add option to fix filename









