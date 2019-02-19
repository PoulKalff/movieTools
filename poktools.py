# Poul Kalff python programming module
# -*- coding: utf-8 -*-

# --- Variables ----------------------------------------------------------------------------------

# --- Functions ----------------------------------------------------------------------------------

def checkPackage(package):
    """ Check whether APT package exists """
    if ' ' in package:
        return -1       # Please specify one pacakge only
    raw_output = runExternal("dpkg -l " + package)
    lines = raw_output.split('\n')
    if len(lines) == 1:
        return False
    else:
        return True

def readFileContents(self, fil):
    """ Read and return file contnts """
    f = open(fil,'r')
    data = f.read()
    f.close()
    return data


def writeFileContents(self, file, content):
""" Write data to file """
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


def runExternal(command):
    """ Runs external process and returns output """
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, stderr=open(os.devnull, 'w'))
    output, err = process.communicate()
    return output


# --- Classes ------------------------------------------------------------------------------------

class FlipSwitch():
    """ Represents a switch with on and off-state """

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
    """ Represents a range of INTs from 0 -> X """

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

# --- Main Program -------------------------------------------------------------------------------

# Module cannot be called directly

# --- TODO ---------------------------------------------------------------------------------------
# -



