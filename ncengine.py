# -*- coding: utf-8 -*-

import re
import sys
import curses
import locale
import poktools

# --- Variables -----------------------------------------------------------------------------------

version = "v0.04"   # change objects
locale.setlocale(locale.LC_ALL, '')

# --- Classes -------------------------------------------------------------------------------------

class nceObject:
	""" A menu where the user can choose between lines of text """

	def __init__(self, _type, _xPos, _yPos, _content, _color, _mWidth, _frame):
		self.type = _type
		self.x = _xPos
		self.y = _yPos
		self.frame = _frame
		self.color = _color
		self.content = _content
		self.maxWidth = _mWidth
		self.visible = True


class NCEngine:
	""" Presents the screen of a program """

	color = { 'white': 0, 'red': 1, 'green' : 2, 'orange' : 3, 'blue' : 4, 'purple' : 5, 'cyan' : 6, 'lightgrey' : 7}	# basic colors
	_status = 'Init'
	_borderColor = False	# no border drawn if no color is set
	lines = []
	objects = {}
	_activeObjectNo = None
	running = True


	def __init__(self):
		self.screen = curses.initscr()
		self.screen.border(0)
		self.screen.keypad(1)
		self.screen.scrollok(0)
		self._getSize()
		curses.noecho()
		curses.curs_set(0)
		# init colors
		curses.start_color()
		curses.use_default_colors()
		for i in range(0, curses.COLORS):
			curses.init_pair(i, i, -1)
		curses.init_pair(200, curses.COLOR_RED, curses.COLOR_WHITE)			# init 256 colors + 1 special
		self._generateID = self.idGenerator()


	def wts(self, xCord, yCord, txt, col=0):
		""" Write to Screen. Wrapper that tests heigth/width before writing to screen  """
		height, width = self.screen.getmaxyx()
		if xCord > height:
		   self.screen.addstr(1, 1, 'WARNING!! Program tried to write BELOW window! (height=' + str(height) + ', X-coordinate=' + str(xCord) + ')', curses.color_pair(0))
		elif yCord > width:
		   self.screen.addstr(1, 1, 'WARNING!! Program tried to write LEFT OF window! (width=' + str(width) + ', Y-coordinate=' + str(yCord) + ')', curses.color_pair(0))
		else:
		   self.screen.addstr(xCord, yCord, str(txt), curses.color_pair(col))
		self.screen.refresh()
		return True


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


	def _getSize(self):
		""" Update height/width/center """
		self.height, self.width = self.screen.getmaxyx()
		self.hcenter = int((self.width - 1) / 2)
		self.vcenter = (self.height - 1) / 2

	def idGenerator(self):
		n = 0
		while True:
			yield n
			n += 1

	def generateID(self):
		""" Get the next sequential ID """
		return next(self._generateID)


	def digitsEditor(self, x, y, eString, color):
		""" Edits digits """
		self._getSize()
		xPos = int((x * self.width / 100) + 2 if type(x) == float else x)
		yPos = int((y * self.height / 100) - 1 if type(y) == float else y)
		pointer = poktools.RangeIterator(len(eString) - 1, False)
		keyPressed = ''
		teRunning = True
		self.wts(self.height - 1, 0, 'UP/DOWN cycles digit, ENTER accepts changes', 6)    # Overwrite Status
		self.screen.refresh()
		while teRunning:
			stringSliced = [eString[:pointer.get()], eString[pointer.get()], eString[pointer.get() + 1:]]
			self.wts(yPos, xPos, stringSliced[0], 5)
			self.wts(yPos, xPos + len(stringSliced[0]), stringSliced[1], 1)
			self.wts(yPos, xPos + len(stringSliced[0]) + len(stringSliced[1]), stringSliced[2], 5)
			self.wts(yPos, xPos + len(stringSliced[0]) + len(stringSliced[1]) + len(stringSliced[2]), ' ', 0)    # overwrite last char
			#self.wts(yPos + 2, xPos + 10, str(stringSliced) + ' - ' + str(keyPressed))      # Message output
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


	def boolEditor(self, x, y, value, color):
		""" Edits True/False """
		bValue = 0 if value == 'False' else 1
		pointer = FlipSwitch(bValue)
		self._getSize()
		self.wts(self.height - 9, 0, 'UP/DOWN changes state, ENTER accepts changes', 6)    # Overwrite Status
		xPos = int((x * self.width / 100) + 2 if type(x) == float else x)
		yPos = int((y * self.height / 100) - 1 if type(y) == float else y)
		teRunning = True
		while teRunning:
			self.wts(yPos, xPos, pointer.getString() + ' ', color)
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


	def textEditor(self, x, y, eString, color):
		""" Edits a line of text """
		pointer = poktools.RangeIterator(len(eString) - 1, False)
		keyPressed = ''
		stringSliced = [[], [], []]
		self._getSize()
		xPos = int((x * self.width / 100) + 2 if type(x) == float else x)
		yPos = int((y * self.height / 100) - 1 if type(y) == float else y)
		self.wts(yPos, xPos, eString, 2)     # overwrite line to edit
		editorRunning = True
		while editorRunning:
			if len(eString) > 0:
				stringSliced[0] = eString[:pointer.get()]
				stringSliced[1] = eString[pointer.get()]
				stringSliced[2] = eString[pointer.get() + 1:]
			self.wts(yPos, xPos, stringSliced[0], color)
			self.wts(yPos, xPos + len(stringSliced[0]), stringSliced[1], 200)
			self.wts(yPos, xPos + len(stringSliced[0]) + len(stringSliced[1]), stringSliced[2], color)
			self.wts(yPos, xPos + len(stringSliced[0]) + len(stringSliced[1]) + len(stringSliced[2]), ' ', 3)    # overwrite last char
# DEBUG		self.wts(20, 2, "Lenght: " + str(len(eString)) + '   Pointer:' + str(pointer.get()) + '   PointerMax:' + str(pointer.max) + '  ' , 4)
# DEBUG		self.wts(21, 2, str(stringSliced) + ' ' , 4)
# DEBUG		self.wts(22, 2, str(len(stringSliced[0])) + ' ' + str(len(stringSliced[1])) + ' ' + str(len(stringSliced[2])) + ' ', 4)
			self.screen.refresh()
			keyPressed = self.screen.getch()
			if keyPressed == 261:            # Cursor RIGHT
				if len(stringSliced[2]) > 0:
					pointer.inc()
			elif keyPressed == 260:          # Cursor LEFT
				if len(stringSliced[0]) > 0:
					pointer.dec()
			elif keyPressed == 10:           # Return (Select)
				editorRunning = False
				return eString.strip()
			elif keyPressed == 330:          # Del
				if stringSliced[2] != ' ':
					stringSliced[1] = stringSliced[2][:1]
					stringSliced[2] = stringSliced[2][1:]
					if stringSliced[2] == '':
						stringSliced[2] = ' '
				elif stringSliced[2] == ' ':
				   stringSliced[1] = ''
				   stringSliced[2] = ' '
			elif keyPressed == 263:          # Backspace
				stringSliced[0] = stringSliced[0][:-1]
				pointer.decMax()
			elif keyPressed < 256 and chr(keyPressed) in ',./-abcdefghijklmnopqrstuvwqyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ':
				stringSliced[1] = chr(keyPressed) + stringSliced[1]
				pointer.incMax()
			if type(stringSliced) == list:
				eString = ''.join(stringSliced)


	def showColors(self):
		""" Show all colors available with their numbers (helper function) """
		sys.exit('notImplemented')


	def render(self):
		""" handles resize and displays the data in "data" """
		if not self.activeObject:
			self.terminate()
			sys.exit('Cannot start program loop without active object. Please set .activeObject')
		self._getSize()
		self.screen.clear()
		if self.width < 60 or self.height < 20:
			self.wts(1, 1, "Windows too small to render!" , 1)
		else:
			# check if resized
			if curses.is_term_resized(self.height, self.width):
				curses.resizeterm(self.height, self.width)
			# render border
			if self._borderColor:
				self.drawBorder()
			# render lines
			self.drawLines()
			# render status
			self.wts(self.height - 1, 1, self._status , 1)
			# render objects
			self.drawObjects()
		self.screen.refresh()


	def drawObjects(self):
		""" Draw all objects in object collection """
		for key, o in self.objects.items():
			posX = int((o.x * self.width / 100) if type(o.x) == float else o.x)
			posY = int((o.y * self.height / 100) - 1 if type(o.y) == float else o.y)
			# frame
			if o.frame:
				if o.maxWidth + o.x < self.width:
					for nr, item in enumerate(o.content):
						self.wts(o.y + nr + 1, o.x, '│ ' + (o.maxWidth * ' ')  + ' │', o.color)
				self.wts(o.y, o.x, '╭─' + ('─' * o.maxWidth) + '─╮', o.color)							# Top
				self.wts(o.y + len(o.content) + 1, o.x, '└─' + ('─' * o.maxWidth) + '─╯', o.color)		# Bottom
			# text
			for nr, item in enumerate(o.content):
				itemColor = o.color
				if o.type == 'MENU':
					itemColor = 200 if nr == o.pointer.get() else o.color
				self.wts(posY + nr + 1, posX + 2, item, itemColor)


	def drawLines(self):
		""" Draw all lines added to object (except border) """
		intersections = [[], []]
		for l in self.lines:
			if l[0] == 'v':
				position = int((l[1] * self.width / 100) if type(l[1]) == float else l[1])
				intersections[0].append(position)
				for yPos in range(1, self.height - 2):
					self.wts(yPos, position, '│', self._borderColor)
				# endpoints
				self.wts(0, position, '┬',self._borderColor)
				self.wts(self.height - 2, position, '┴', self._borderColor)
			elif l[0] == 'h':
				position = int((l[1] * self.height / 100) - 1 if type(l[1]) == float else l[1])
				intersections[1].append(position)
				self.wts(position, 1, '─' * (self.width - 2), self._borderColor)
				# endpoints
				self.wts(position, 0, '├', self._borderColor)
				self.wts(position, self.width - 1, '┤', self._borderColor)
		# draw intersections
		for x in intersections[1]:
			for y in intersections[0]:
				self.wts(x, y, '┼', self._borderColor)


	def drawBorder(self):
		""" Draw the staic border of the screen """
		# horizontal lines
		self.wts(0, 0, '╭' + '─' * (self.width - 2) + '╮', self._borderColor)						# Top
		self.wts(self.height - 2, 0, '└' + '─' * (self.width - 2) + '╯', self._borderColor)			# Bottom
		# vertical lines
		for yPos in range(1, self.height - 2):
			self.wts(yPos, 0, '│', self._borderColor)
			self.wts(yPos, self.width - 1, '│', self._borderColor)


	def getInput(self):
		""" Retrieve input and handle internally if understood, else return to calling program """
		keyPressed = self.screen.getch()
		if keyPressed == 113:		# <escape>
			self.terminate()
			self.running = False
		elif keyPressed == 259:		# KEY_UP
			self.activeObject.pointer.dec()
		elif keyPressed == 258:		# KEY_DOWN
			self.activeObject.pointer.inc()
		elif keyPressed == 260:		# KEY_LEFT
			pass
		elif keyPressed == 261:		# KEY_RIGHT
			pass
		else:
			return keyPressed


	def terminate(self):
		# Set everything back to normal
		self.screen.keypad(0)
		curses.echo()
		curses.nocbreak()
		curses.endwin()


# --- Setter Functions ----------------------------------------------------------------------------

	@property
	def pointer(self):
		return self.objects[self._activeObjectNo].pointer.get()

	@property
	def borderColor(self):
		return self._borderColor

	@borderColor.setter
	def borderColor(self, val):
		self._borderColor = self.color[val.lower()] if type(val) == str else val

	@property
	def activeObject(self):
		if self._activeObjectNo:
			return self.objects[self._activeObjectNo]
		else:
			return None

	@activeObject.setter
	def activeObject(self, val):
		self._activeObjectNo = val if val < len(self.objects) else None
		if not self._activeObjectNo:
			sys.exit('No object number ' + str(val))

	@activeObject.setter
	def status(self, val):
		self._status = val

	def addGridLine(self, type, coordinate):
		self.lines.append([type, coordinate])

	def addLabel(self, x, y, item, color):
		maxLength = len(item)
		id = self.generateID()
		self.objects[id] = nceObject('LABEL', x, y, [item], color, maxLength, False)
		return id

	def addTextbox(self, x, y, items, color, frame):
		maxLength = len(max(items, key=lambda coll: len(coll)))
		id = self.generateID()
		self.objects[id] =  nceObject('TEXTBOX', x, y, items, color, maxLength, frame)
		return id

	def addMenu(self, x, y, items, color, frame):
		items = list(map(str, items))	# ensure list items are string-type
		maxLength = len(max(items, key=lambda coll: len(coll)))
		id = self.generateID()
		obj = nceObject('MENU', x, y, items, color, maxLength, frame)
		obj.pointer = poktools.RangeIterator(len(items) - 1, False)
		self.objects[id] = obj
		return id





# --- Main ---------------------------------------------------------------------------------------

if sys.version_info < (3, 0):
	sys.stdout.write("Sorry, requires Python 3.x\n")
	sys.exit(1)



# --- TODO ---------------------------------------------------------------------------------------
# - BUG 	  : Stadigt problemer med scroll/count af bytes..... (??)
# - BUG		  : Crasher stadigt hvis window bliver minimalt I HOEJDE!!
# - FEATURE	  : lave properties til alt, som kan indstilles
# - DOKUMENTATION : Lav mindst simpel dokumentation af hver funktion
# - Status mangler for alle editors ..... pånær digitseditor
# - Status skal have en fast farve
# - En form for funktion hvor man kan tilfoeje colour-init-pairs, ud over default......addColor(c1, c2='Black')
# - Et kald hvor man kan tilfoeje keyboard-keys, og definere hvad der skal ske hvis de bliver kaldt
# - Hvad/hvordan skal pointeren defineres....? Der skal kun vaere EEN!
# - En funktion addData() som tilfoejer data til current frame, og en funktion drawFrame() som tegner denne og tømmer buffer. Boer beregne/optimere data, f.eks. intersects



