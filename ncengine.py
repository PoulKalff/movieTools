# -*- coding: utf-8 -*-

import os
import re
import sys
import curses
import locale
import poktools

# --- Variables -----------------------------------------------------------------------------------

version = "v0.07"   # fixed tabs
locale.setlocale(locale.LC_ALL, '')

# --- Functions -----------------------------------------------------------------------------------


# --- Classes -------------------------------------------------------------------------------------

class File:
	""" Slave class used by SelectPath """
	def __init__(self, name):
		self.name = name
	def pad(self, data, width):
		return data + ' ' * (width - len(data))
	def render(self, depth, width):
		return self.pad('%s%s %s' % (' ' * 4 * depth, self.icon(), os.path.basename(self.name)), width)
	def icon(self): return '   '
	def traverse(self): yield self, 0
	def expand(self): pass
	def collapse(self): pass


class Dir(File):
	""" Slave class used by SelectPath """

	def __init__(self, name):
		File.__init__(self, name)
		try: self.kidnames = sorted(os.listdir(name))
		except: self.kidnames = None  # probably permission denied
		self.kids = None
		self.expanded = False
	def factory(self, name):    # copy of parent, rather than sending it with object
		if os.path.isdir(name): return Dir(name)
		else: return File(name)
	def children(self):
		if self.kidnames is None: return []
		if self.kids is None:
			self.kids = [self.factory(os.path.join(self.name, kid))
				for kid in self.kidnames]
		return self.kids
	def icon(self):
		if self.expanded: return '[-]'
		elif self.kidnames is None: return '[?]'
		elif self.children(): return '[+]'
		else: return '[ ]'
	def expand(self): self.expanded = True
	def collapse(self): self.expanded = False
	def traverse(self):
		yield self, 0
		if not self.expanded: return
		for child in self.children():
			for kid, depth in child.traverse():
				yield kid, depth + 1


class SelectPath:
	""" Presents a curses screen where user can select a path / file, returns result """

	def __init__(self, pScreen, startDir="/"):
		self.startDir = startDir
		self.screen = pScreen
		self.selected = False
		mydir = self.factory(self.startDir)
		mydir.expand()
		curidx = 3
		pending_action = None
		pending_save = False
		while 1:
			self.screen.clear()
			line = 0
			offset = max(0, curidx - curses.LINES + 3)
			for data, depth in mydir.traverse():
				if line == curidx:
					self.screen.attrset(curses.color_pair(7) | curses.A_BOLD)
					if pending_action:
						getattr(data, pending_action)()
						pending_action = None
					elif pending_save:
						self.selected = data.name
						return
				else:
					self.screen.attrset(curses.color_pair(0))
				if 0 <= line - offset < curses.LINES - 1:
					self.screen.addstr(line - offset, 0, data.render(depth, curses.COLS))
				line += 1
			pending_save = False
			self.screen.refresh()
			ch = self.screen.getch()
			if ch == curses.KEY_UP: curidx -= 1
			elif ch == curses.KEY_DOWN: curidx += 1
			elif ch == curses.KEY_PPAGE:
				curidx -= curses.LINES
				if curidx < 0: curidx = 0
			elif ch == curses.KEY_NPAGE:
				curidx += curses.LINES
				if curidx >= line: curidx = line - 1
			elif ch == curses.KEY_RIGHT: pending_action = 'expand'
			elif ch == curses.KEY_LEFT: pending_action = 'collapse'
			elif ch == 27 or ch == 113: return    # <return> or 'q'
			elif ch == ord('\n'): pending_save = True
			curidx %= line

	def factory(self, name):
		""" Slave function, to build up path """
		if os.path.isdir(name): return Dir(name)
		else: return File(name)


# --- Object CLasses -----------------------------------------------------------------------

class nceLine:
	""" Line object"""

	def __init__(self, direction, coord):
		self.type = 'Line'
		self.coordinate = coord
		self.direction = direction
		self.visible = True
		self.color = 3


class nceObject:
	""" nce object for inherit """

	def __init__(self, x, y, content):
		self.x = x
		self.y = y
		self.color = 3
		self.content = content
		self.visible = True
		self.frame = False


class nceLabel(nceObject):
	""" Label object"""

	def __init__(self, x, y, content):
		super().__init__(x, y, content)
		self.type = 'LABEL'


class nceDialogBox(nceObject):
	""" Dialog object, which can only be YES or NO """

	def __init__(self, x, y):
		super().__init__(x, y, [])
		self.type = 'DIALOGBOX'
		self.answer = False
		self.content = []
		self.content.append(['        NO!        ', 16])
		self.content.append(['        YES        ', 3])
		self.maxWidth = 3
		self.pointer = poktools.FlipSwitch(0)


	def updateKeys(self, _key):
		""" Recieves keys and moves on self. """
		if _key == curses.KEY_UP or _key == curses.KEY_DOWN:
			self.switch()
		elif _key == 261 or _key == 10:           # Execute (Key RIGHT / ENTER)
			return str(self.pointer.get())
		return (50, _key)		# send key back, to handle in main program

	def switch(self, _color = 16):
		""" Changes the marked selection"""
		self.pointer.flip()

		if self.pointer.get():
			self.content[0][1] = 3
			self.content[1][1] = 16
		else:
			self.content[0][1] = 16
			self.content[1][1] = 3


class nceTextBox(nceObject):
	""" TextBox object """

	def __init__(self, x, y, content):
		super().__init__(x, y, content)
		self.type = 'TEXTBOX'

	def highlight(self, highlightedItem):
		""" Set all items to default color and highlight one """
		for nr, i in enumerate(self.content):
			self.content[nr][1] = 16 if nr == highlightedItem else self.content[nr][2]

	def colorFrame(self, _color):
		""" Sets the color of the frame of the object, if object has a frame """
		if self.frame:
			for nr, i in enumerate(self.frame):
				self.frame[nr][1] = _color



class nceMenu(nceObject):
	""" Menu object """

	def __init__(self, x, y, content):
		super().__init__(x, y, content)
		self.type = 'MENU'
		self.id = None
		self.pointer = poktools.RangeIterator(len(self.content) - 1, False)
		self.actions = []		# actions bound to menu content
		self.linkedObjects = []		# objects that have identical content and are highlighted from this menu


	def highlight(self, highligtedItem):
		""" Set all items to default color and highlight one"""
		for nr, i in enumerate(self.content):
			self.content[nr][1] = self.content[nr][2]
		self.content[highligtedItem][1] =  16


	def colorFrame(self, _color):
		""" Sets the color of the frame of the object, if object has a frame """
		if self.frame:
			for nr, i in enumerate(self.frame):
				self.frame[nr][1] = _color


	def updateKeys(self, _key):
		""" Recieves keys and moves on self. """
		if _key == curses.KEY_UP:
			self.pointer.dec(1)
		elif _key == curses.KEY_DOWN:
			self.pointer.inc(1)
		elif _key == 261 or _key == 10:           # Execute (Key RIGHT / ENTER)
			if len(self.actions) == 0:
				pass
			elif len(self.actions) == 1:	# If only one action, execute this, no matter what menu entry is selected
				self.actions[0]()
			elif len(self.actions) == len(self.content):
				self.actions[self.pointer.get()]()
		self.highlight(self.pointer.get())
		# highlight linked objects
		for o in self.linkedObjects:
			o.highlight(self.pointer.get())
		return (self.id, _key)		# send key back, to handle in main program


class NCEngine:
	""" Presents the screen of a program """

	_borderColor = 0
	lines = []
	objects = []		# any object that cannot have control/focus
	menus = []
	running = True
	screenBorder = False

	def __init__(self, parent):
		self.screen = curses.initscr()
		self.screen.border(0)
		self.screen.keypad(1)
		self.screen.scrollok(0)
		self._getSize()
		self.parent = parent
		self.status = 'Init'
		curses.noecho()
		curses.curs_set(0)
		# init colors
		curses.start_color()
		curses.use_default_colors()
		for i in range(1, curses.COLORS):
			curses.init_pair(i, i, -1)
		curses.init_pair(16, curses.COLOR_RED, curses.COLOR_WHITE)	# special selection color


	def wts(self, xCord, yCord, txt, col=0):
		""" Write to Screen. Wrapper that tests heigth/width before writing to screen  """
		height, width = self.screen.getmaxyx()
		txt = txt[:width - yCord]	# do not draw outside screen
		if xCord > height:
			 self.screen.addstr(1, 1, 'WARNING!! Program tried to write BELOW window! (height=' + str(height) + ', X-coordinate=' + str(xCord) + ')', curses.color_pair(0))
		elif yCord > width:
			 self.screen.addstr(1, 1, 'WARNING!! Program tried to write LEFT OF window! (width=' + str(width) + ', Y-coordinate=' + str(yCord) + ')', curses.color_pair(0))
		else:
			self.screen.addstr(xCord, yCord, str(txt), curses.color_pair(col))
		return True


	def _getSize(self):
		""" Update height/width/center """
		self.height, self.width = self.screen.getmaxyx()
		self.hcenter = int((self.width - 1) / 2)
		self.vcenter = (self.height - 1) / 2
#		self.wts(self.height - 3, 0, str(self.hcenter), 6)	# Debug


	def digitsEditor(self, x, y, eString, color):			# UTESTET!
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


	def boolEditor(self, x, y, value, color):			# UTESTET!
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
		eString += ' '
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
			self.wts(yPos, xPos + len(stringSliced[0]), stringSliced[1], 20)
			self.wts(yPos, xPos + len(stringSliced[0]) + len(stringSliced[1]), stringSliced[2], color)
			self.wts(yPos, xPos + len(stringSliced[0]) + len(stringSliced[1]) + len(stringSliced[2]), ' ', 3)    # overwrite last char
#			self.wts(20, 2, "Lenght: " + str(len(eString)) + '   Pointer:' + str(pointer.get()) + '   PointerMax:' + str(pointer.max) + '  ' , 4)
#			self.wts(21, 2, str(stringSliced) + ' ' , 4)
#			self.wts(22, 2, str(len(stringSliced[0])) + ' ' + str(len(stringSliced[1])) + ' ' + str(len(stringSliced[2])) + ' ', 4)
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
		colors = ['white', 'red', 'green', 'orange', 'blue', 'purple', 'cyan', 'lightgrey',
				 'darkgrey', 'light red', 'light green', 'yellow', 'light blue', 'purple', 'cyan', 'dark white']
		max = curses.COLORS if curses.COLORS <= 16 else 16
		self.screen.clear()
		for c in range(0, max):
			self.wts(c + 2, 1, "color " + str(c) + ' : ' + colors[c], c)
		self.wts(18, 1, "color 16 : red on white", 16)
		self.wts(20, 1, 'Color demo, displaying ' + str(max) + ' colors + 1 special')
		self.screen.refresh()
		ch = False
		while not ch:
			ch = self.screen.getch()
		self.exit('Color demo complete')


	def render(self):
		""" handles resize and displays the data in "data" """
		self._getSize()
		self.screen.clear()
		if self.width < 60 or self.height < 20:
			self.wts(1, 1, "Windows too small to render!" , 1)
		else:
			# check if resized
			if curses.is_term_resized(self.height, self.width):
				curses.resizeterm(self.height, self.width)
				self._getSize()
			# render border
			if self.screenBorder:
				self.drawBorder()
			# render lines
			self.drawLines()
			# render status
			self.wts(self.height - 1, 1, self.status , 1)
			# render objects
			self.drawObjects(self.objects)
			# render menus
			self.drawObjects(self.menus)
		self.screen.refresh()


	def updateStatus(self, newStatus = False):
		""" Update status, from the calling program """
		height, width = self.screen.getmaxyx()
		if newStatus:
			self.status = str(newStatus)
		spaces = width - len(self.status) - 2
		self.wts(height - 1, 1, self.status + ' ' * spaces , 1)
		self.screen.refresh()


	def drawObjects(self, objects):
		""" Draw all objects in object collection """
		for o in objects:
			if o.visible:
				if o.rtc:	# only horisontal center is supported currently, and only absolute values
					hcenter = int((self.width - 1) / 2)
					posX = hcenter + o.x
					posY = o.y
				else:
					posX = int((o.x * self.width / 100) if type(o.x) == float else o.x)
					posY = int((o.y * self.height / 100) - 1 if type(o.y) == float else o.y)
				# frame
				if o.frame:
					for nr, item in enumerate(o.frame):
						self.wts(posY + nr, posX + 1, item[0], item[1])
				# text
				for nr, item in enumerate(o.content):
					for coord in self.verticalBoundaries:	# Check if a line is crossed
						if coord > posY and coord < posY + len(item[0]):
							if len(self.menus) == 1:
								item[0] = item[0][:coord - posY - 2] + '..'
					try:
						self.wts(posY + nr + 1, posX + 2, item[0], item[1])
					except:
						self.exit('Error occured in drawObjects, while drawing : OBJECT= "' + str(o.content) + '" ITEM= "' + str(item)) + '"'
		return True


	def drawLines(self):
		""" Draw all lines added to object (except border) """
		intersections = [[], []]
		for l in self.lines:
			if l.direction == 'v':
				if l.rtc:
					position = l.coordinate + int((self.width - 1) / 2)
				else:
					position = int((l.coordinate * self.width / 100) if type(l.coordinate) == float else l.coordinate)
				intersections[0].append(position)
				for yPos in range(1, self.height - 2):
					self.wts(yPos, position, '│', self._borderColor)
				# endpoints
				self.wts(0, position, '┬',self._borderColor)
				self.wts(self.height - 2, position, '┴', self._borderColor)
			elif l.direction == 'h':
				if l.rtc:
					position = l.coordinate + ((self.height - 1) / 2)
				else:
					position = int((l.coordinate * self.height / 100) - 1 if type(l.coordinate) == float else l.coordinate)
				intersections[1].append(position)
				self.wts(position, 1, '─' * (self.width - 2), self._borderColor)
				# endpoints
				self.wts(position, 0, '├', self._borderColor)
				self.wts(position, self.width - 1, '┤', self._borderColor)
		# draw intersections
		for x in intersections[1]:
			for y in intersections[0]:
				self.wts(x, y, '┼', self._borderColor)
		self.verticalBoundaries = intersections[0]
		if self.screenBorder:
			self.verticalBoundaries.append(self.width)


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
		return keyPressed 		# return key for (possible) further action in calling program


	def terminate(self):
		# Set everything back to normal
		self.screen.keypad(0)
		curses.echo()
		curses.nocbreak()
		curses.endwin()


	def exit(self, _exitMessage):
		# Set everything back to normal
		self.running = False
		self.screen.keypad(0)
		curses.echo()
		curses.nocbreak()
		curses.endwin()
		if type(_exitMessage) == list:
			print('--- Exit List dump begin -----------------------------')
			for item in _exitMessage:
				print('  ' + str(item))
			print('--- Exit List dump end -------------------------------\n')
		elif type(_exitMessage) == dict:
			print('--- Exit Dict dump begin -----------------------------')
			for key, val in _exitMessage.items():
				print('  ' + str(key) + ' : ' + str(val))
			print('--- Exit Dict dump end -------------------------------\n')
		else:
			sys.exit(str(_exitMessage))


# --- Setter Functions ----------------------------------------------------------------------------

	@property
	def borderColor(self):
		return self._borderColor

	@borderColor.setter
	def borderColor(self, val):
		self._borderColor = self.color[val.lower()] if type(val) == str else val

	# Helper function
	def createFrame(self, content):
		result = []
		maxWidth = len(max(content))
		result.append(['╭' + ('─' * (maxWidth)) + '╮', 3])        # Top
		self.contentItems = len(content)
		for i in range(self.contentItems):
			result.append(['│' + (' ' * (maxWidth))  + '│', 3])
		result.append(['└' + ('─' * (maxWidth)) + '╯', 3])        # Bottom
		return result


	def addGridLine(self, type, pos, rtc, visible=True):
		obj = nceLine(type, pos)
		obj.rtc = True if rtc else False
		obj.visible = visible
		obj.color = 3
		self.lines.append(obj)
		return obj


	def addLabel(self, x, y, content, color, rtc, visible=True):
		obj = nceLabel(x, y, [[content, color]])
		obj.rtc = True if rtc else False
		obj.frame = False
		obj.maxWidth = len(content)
		obj.visible = visible
		self.objects.append(obj)
		return obj


	def addTextBox(self, x, y, content, frame, rtc, visible=True):
		obj = nceTextBox(x, y, content)
		obj.rtc = True if rtc else False
		obj.frame = self.createFrame(items) if frame else False
		obj.maxWidth = len(max(content))
		obj.visible = visible
		obj.highlight(0)
		self.objects.append(obj)
		return obj


	def addDialogBox(self, color):
		""" Always appears in the center """
		self._getSize()
		obj = nceDialogBox(self.hcenter - 11, 10)
		obj.rtc = False
		obj.frame = [	['╭' + ('─' * 19) + '╮', 3],
						['│' + (' ' * 19) + '│', 3],
						['│' + (' ' * 19) + '│', 3],
						['└' + ('─' * 19) + '╯', 3]]
		obj.visible = True
		obj.color = color
		self.menus.append(obj)
		return obj


	def addMenu(self, ID, x, y, content, frame, rtc, visible=True):
		obj = nceMenu(x, y, content)
		obj.rtc = True if rtc else False
		obj.frame = self.createFrame(content) if frame else False
		obj.maxWidth = len(max(content))
		obj.visible = visible
		obj.id = ID
		obj.highlight(0)
		self.menus.append(obj)
		return obj



# --- Main ---------------------------------------------------------------------------------------

if sys.version_info < (3, 0):
	sys.stdout.write("Sorry, requires Python 3.x\n")
	sys.exit(1)



# --- TODO ---------------------------------------------------------------------------------------
# - BUG		  : Crasher stadigt hvis window bliver minimalt I HOEJDE!!
# - Position objects relative to RIGHT SIDE / BOTTOM / VERTICAL CENTER
# - Boer kunne overskrive ESC => QUIT, saa den kan bruges til noget andet
# - Mulighed for CENTER i alle menuer/testboxe (for at undgaa "    MENU    ")
# - Dialogbox not functional yet
