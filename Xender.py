# -*- coding: utf-8 -*-

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys 
import subprocess 
import os

from threading import Thread
from PyQt5.QtCore import QFileInfo, QUrl, QTimer, QSize, Qt
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem, QMainWindow, QWidget, QGridLayout, 
                            QToolButton, QFrame, QLabel, QPushButton, QApplication)
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineDownloadItem


os.chdir('resources')
# Global URL Variable Used for setting browser URL
URL = QFileInfo('index.htm').absoluteFilePath()

def connect(browser):
    '''
    Checks for the IP Address of the WiFi Hotspot Server
    All errors in connection are handled
    '''
    global URL
    raw = subprocess.check_output('ipconfig',shell=True) # runs 'ipconfig' on cmd
    text = raw.decode('utf-8') # decode to string
    lines = []
    for line in text.splitlines():
        lines.append(line.lower())
    try:
        # Check if adapter is availabe
        wifi_index = lines.index('wireless lan adapter wi-fi:')
        wifi_info = lines[wifi_index:len(lines)]
    except ValueError:
        # If WiFi adapter is not available
        print('Wi-Fi is not available on this system')
        URL = QFileInfo('no-wifi.htm').absoluteFilePath()
        return
    
    try:
        # Check if it is  connected to a network
        test_index = wifi_index+2
        if lines[test_index].endswith('media disconnected'):
            raise ConnectionError
        gateway = ''
        for line in wifi_info:
            if 'default gateway' in line:
                gateway = line
                break

        if gateway =='':
            raise ConnectionError
        
        if gateway.count(':')>1: # IpV6 address
            try:
                gateway = wifi_info[wifi_info.index(gateway)+1].strip()
            except IndexError:
                raise ConnectionError
        
    except ConnectionError:
        # If it is not connected
        print('Wi-Fi is not connected. Connect to your phone')
        URL = QFileInfo('not-connected.htm').absoluteFilePath()
        return
    
    # If all conditions are positive the final Url is set
    URL = 'http://'+gateway.split(':')[-1].strip()+':33455'

class DownloadItem(QTreeWidgetItem):
    '''
    Registers, manages and ends download
    '''
    def __init__(self, treeWidget, downloadItem, window):
        QTreeWidgetItem.__init__(self, treeWidget)
        self.icons = {'inprogress': QIcon('res/Down.png'),
                      'finished': QIcon('res/file.png'),
                      'paused': QIcon('res/pause.png'),
                      'failed': QIcon('res/alert-box.png'),
                      'cancelled':QIcon('res/alert-box.png'),
                      }
        
        self.window = window # mainWindow
        self.downloadItem = downloadItem # QWebEngineDownloadItem

        # Connect signals and slots
        self.downloadItem.finished.connect(self.finished)
        self.downloadItem.downloadProgress.connect(self.download_progess)
        self.downloadItem.stateChanged.connect(self.state_changed)
        self.downloadItem.isPausedChanged.connect(self.paused_changed)

        # Set properies
        self.path = self.downloadItem.path()
        self.url = self.downloadItem.url().toString()
        self.folder = self.downloadItem.downloadDirectory()
        self.name = self.downloadItem.downloadFileName()
        self.status = 'Waiting'
        self.size = ''
        self.state = 'inprogress'
        self.valid = True # Valid until cancelled or failed
        self.update_data()
    
    def download_progess(self, bytes_received, bytes_total):
        # To handle download progress
        if self.valid:
            self.size = self.get_size(bytes_total)
            if bytes_total==0 or bytes_total==-1:
                progress = ''
                self.status = 'In Progress'
            else:
                progress = str(int(100 * bytes_received / bytes_total))+'%'
                self.status = 'In Progress ('+progress+')'
            self.update_data()
        
    def get_size(self, size_bytes):
        '''Convert bytes to KB, MB and GB'''
        if size_bytes>1000000000:
            calc_size = round(size_bytes/1000000000,1)
            unit = 'GB'
        elif size_bytes>1000000:
            calc_size = round(size_bytes/1000000,1)
            unit = 'MB'
        elif size_bytes>1000:
            calc_size = round(size_bytes/1000,1)
            unit = 'KB'
        elif size_bytes==0 or size_bytes==-1:
            calc_size = ''
            unit = 'Unknown'
        else:
            calc_size = size_bytes
            unit = 'B'
        
        size_text = str(calc_size)+' '+unit
        return size_text
    
    def update_data(self):
        ''' Update visible data on the downloadWidget'''
        self.setIcon(0, self.icons[self.state])
        self.setData(0, 0, self.name)
        self.setData(1, 0, self.status)
        self.setData(2, 0, self.size)
    
    def state_changed(self, state):
        '''Manage state changes'''
        self.window.hideDownloadActions()

        if state == QWebEngineDownloadItem.DownloadState.DownloadRequested:
            self.state = 'inprogress'
            self.state = 'Waiting'
            self.update_data()
        elif state == QWebEngineDownloadItem.DownloadState.DownloadInProgress:
            self.state = 'inprogress'
            self.status = 'In progress'
            self.update_data()
        elif state == QWebEngineDownloadItem.DownloadState.DownloadCompleted:
            self.state = 'finished'
            self.status = 'Completed'
            if not os.path.isfile(self.path):
                self.valid = False
                self.state = 'cancelled'
                self.status = 'Cancelled'
            self.update_data()
        elif state == QWebEngineDownloadItem.DownloadState.DownloadCancelled:
            self.valid = False
            self.state = 'cancelled'
            self.status = 'Cancelled'
            self.update_data()
        else:
            self.valid = False
            self.state = 'failed'
            self.status = 'Failed'
            print('Download Failed')
            self.update_data()
            
    def paused_changed(self, paused):
        '''Manage pause and resume events'''
        if paused:
            self.state = 'paused'
            self.status = 'Paused'
        else:
            self.state = 'inprogress'
            self.status = 'Resuming'
        self.update_data()

    def finished(self):
        '''Manage download completed event'''
        self.state = 'finished'
        self.status = 'Completed'
        if not os.path.isfile(self.path):
            self.valid = False
            self.state = 'cancelled'
            self.status = 'Cancelled'
        self.update_data()

    def pause(self):
        self.downloadItem.pause()

    def resume(self):
        self.downloadItem.resume()

    def cancel(self):
        self.downloadItem.cancel()

    def remove(self):
        self.setHidden(True)
        self.window.downloadItems.remove(self)


class MainWindow(QMainWindow):
    '''User Interface and other micro tasks'''
    def __init__(self):
        QMainWindow.__init__(self)
        # MainWindow setting
        self.setWindowTitle('Xender for PC')
        self.setWindowIcon(QIcon('icon.png'))
        # Icon dictionary
        self.icons = {'resume': QIcon('res/resume.png'),
                      'remove': QIcon('res/delete.png'),
                      'pause': QIcon('res/pause.png'),
                      'retry': QIcon('res/179407.png'),
                      'cancel':QIcon('res/stop.png'),
                      'open': QIcon('res/file.png')}  
         
        # Window internals
        self.widget = QWidget()
        self.setCentralWidget(self.widget)
        layout = QGridLayout(self.widget)
        layout.setContentsMargins(0,0,0,0)

        # Other properties
        self.url = QFileInfo('index.htm').absoluteFilePath()
        self.showDownload = False
        self.downloadItems = []

        # Browser widget
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(self.url))
        self.browser.setAcceptDrops(True)
        layout.addWidget(self.browser)

        #Timer
        self.timer = QTimer() # Periodic updates timer
        self.timer.start(250)
        self.hideTimer = QTimer() # Hide download frame and panel timer

        # Reconnect button
        self.reconnectButton = QToolButton(self.widget)
        self.reconnectButton.setText('Reconnect')
        icon = QIcon('res/179407.png')
        self.reconnectButton.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.reconnectButton.setIconSize(QSize(36,36))
        self.reconnectButton.setIcon(icon)
        self.reconnectButton.setFixedSize(60,60)
        buttonPos = (self.size().width()-80 , self.size().height()-80)
        self.reconnectButton.move(buttonPos[0],buttonPos[1])
        self.reconnectButton.clicked.connect(self.reconnect)
        self.reconnectButton.hide()

        # Download button( to show downloads)
        self.downloadButton = QToolButton(self.widget)
        self.downloadButton.setText('Downloads')
        icon = QIcon('res/Down.png')
        self.downloadButton.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.downloadButton.setIconSize(QSize(36,36))
        self.downloadButton.setIcon(icon)
        self.downloadButton.setFixedSize(60,60)
        buttonPos = (self.size().width()-80 , 60)
        self.downloadButton.move(buttonPos[0],buttonPos[1])
        self.downloadButton.clicked.connect(self.toggleDownload)
        self.downloadButton.hide()

        # Download notice panel
        self.panel = QFrame(self.widget)
        self.panel.setFixedSize(300,60)
        self.panel.setStyleSheet('background: #ffffff;border: 1px solid #b9b9b9;')
        panelPos = (self.size().width()-390, 60)
        self.panel.move(panelPos[0], panelPos[1])
        self.panelLayout = QGridLayout(self.panel)
        text = '''<b>Note:</b> All downloads last for a session. Downloads are cleared 
        upon log out or reconnection. However files of completed downloads will be preserved.'''
        self.totalDownload = QLabel(text)
        self.totalDownload.setWordWrap(True)
        self.totalDownload.setStyleSheet('border: 0px solid #000000')
        self.panelLayout.addWidget(self.totalDownload, 0,0)
        self.panel.hide()

        # Download frame
        self.frame = QFrame(self.widget)
        self.frame.setFixedSize(370,260)
        framePos = (self.size().width()-390, 130)
        self.frame.move(framePos[0], framePos[1])
        self.frameLayout = QGridLayout(self.frame)
        self.frameLayout.setContentsMargins(0,0,0,0)
        self.downloadWidget = QTreeWidget()
        self.buttonA = QPushButton('Pause')
        self.buttonB = QPushButton('Cancel')
        self.buttonC = QPushButton('Show in Explorer')
        self.buttonC.setIcon(QIcon('res/open.png'))
        self.buttonA.clicked.connect(self.buttonA_handle)
        self.buttonB.clicked.connect(self.buttonB_handle)
        self.buttonC.clicked.connect(self.buttonC_handle)
        self.hideDownloadActions()
        self.frameLayout.addWidget(self.downloadWidget, 0,0,1,3)
        self.frameLayout.addWidget(self.buttonA, 1,0)
        self.frameLayout.addWidget(self.buttonB, 1,1)
        self.frameLayout.addWidget(self.buttonC, 1,2) 
        self.frame.hide()  

        # Download Widget
        self.downloadWidget.setRootIsDecorated(False)
        self.downloadWidget.currentItemChanged.connect(self.updateButtons)
        self.downloadWidget.clicked.connect(self.updateButtons)
        self.downloadWidget.setAlternatingRowColors(True)
        self.downloadWidget.setAllColumnsShowFocus(False)
        self.downloadWidget.setColumnWidth(0,160)
        self.downloadWidget.setDragEnabled(False)
        self.downloadWidgetHeader = self.downloadWidget.headerItem()
        self.downloadWidgetHeader.setText(0, 'Name')
        self.downloadWidgetHeader.setText(1, 'Status')
        self.downloadWidgetHeader.setText(2, 'Size')

        # List of pages available offline
        self.offlinePages = ['connecting.htm', 'help.htm','index.htm','no-wifi.htm',
                             'not-connected.htm', 'not-open.htm','about.htm','gnu-gplv3.htm']
        
        # Connect Signals and Slots
        self.timer.timeout.connect(self.updateApp)
        self.hideTimer.timeout.connect(self.hideDownload)
        self.browser.urlChanged.connect(self.handleUrlChange)
        self.browser.loadFinished.connect(self.loadFinished)
        self.browser.page().profile().downloadRequested.connect(self.download)
       
        # Display window
        self.setMinimumSize(QSize(640,480))
        self.showMaximized()
        self.show()
    
    def download(self, item):
        '''Function to initiate downloads
            To delete failed downloads'''
        
        # To stop failed or cancelled downloads from reinitaiting
        for old_item in self.downloadItems:
            if old_item.path == item.path():
                old_item.remove()
        
        item.accept()
        downloadItem = DownloadItem(self.downloadWidget, item, self)
        self.downloadItems.append(downloadItem)
        
    def updateButtons(self):
        '''
        To update text and icon on the action buttons
        based on the state of the downloadItem
        '''
        item = self.downloadWidget.currentItem()
        if not item:
            return
        if item.state == 'inprogress':
            self.buttonA.setText('Pause')
            self.buttonA.setIcon(self.icons['pause'])
            self.buttonB.setText('Cancel')
            self.buttonB.setIcon(self.icons['cancel'])
        elif item.state == 'paused':
            self.buttonA.setText('Resume')
            self.buttonA.setIcon(self.icons['resume'])
            self.buttonB.setText('Cancel')
            self.buttonB.setIcon(self.icons['cancel'])
        elif item.state == 'failed':
            self.buttonA.setText('Retry')
            self.buttonA.setIcon(self.icons['retry'])
            self.buttonB.setText('Remove')
            self.buttonB.setIcon(self.icons['remove'])
        elif item.state == 'finished':
            self.buttonA.setText('Open')
            self.buttonA.setIcon(self.icons['open'])
            self.buttonB.setText('Remove')
            self.buttonB.setIcon(self.icons['remove'])
        elif item.state == 'cancelled':
            self.buttonA.setText('Retry')
            self.buttonA.setIcon(self.icons['retry'])
            self.buttonB.setText('Remove')
            self.buttonB.setIcon(self.icons['remove'])
        self.showDownloadActions()
    
    def hideDownloadActions(self):
        '''Hide action button to prevent event overload'''
        self.buttonA.hide()
        self.buttonB.hide()
        self.buttonC.hide()
        self.downloadWidget.clearSelection()
    
    def showDownloadActions(self):
        '''Show action button to perform actions on downloadItem'''
        self.buttonA.show()
        self.buttonB.show()
        self.buttonC.show()
    
    def buttonA_handle(self):
        '''Handle events from buttonA based on the text'''
        item = self.downloadWidget.currentItem()
        text =self.buttonA.text()
        if not item:
            return
        if text == 'Pause':
            item.pause()
        elif text == 'Resume':
            item.resume()
        elif text == 'Retry':
            url = item.url
            item.remove()
            self.browser.setUrl(QUrl(url))
        elif text == 'Open':
            QDesktopServices.openUrl(QUrl.fromLocalFile(item.path))

        self.hideDownloadActions()
    
    def buttonB_handle(self):
        '''Handle events from buttonB based on the text'''
        item = self.downloadWidget.currentItem()
        text =self.buttonB.text()
        if not item:
            return
        if text=='Cancel':
            item.cancel()
        elif text=='Remove':
            item.remove()
        self.hideDownloadActions()
    
    def buttonC_handle(self):
        '''Handle events from buttonC
        Open explorer and select the requested file'''
        item = self.downloadWidget.currentItem()
        if not item:
            return
        path = item.path.replace('/','\\')
        subprocess.Popen('explorer /select,"'+path+'"')
        self.hideDownloadActions()
    
    def resizeEvent(self, e):
        '''To move Download, and Reconnect buttons 
        Panel and frame position accordingly based on window size'''
        buttonPos = (self.size().width()-80 , self.size().height()-80)
        self.reconnectButton.move(buttonPos[0], buttonPos[1])
        buttonPos = (self.size().width()-80 , 60)
        self.downloadButton.move(buttonPos[0],buttonPos[1])
        panelPos = (self.size().width()-390, 60)
        self.panel.move(panelPos[0], panelPos[1])
        framePos = (self.size().width()-390, 130)
        self.frame.move(framePos[0], framePos[1])
    
    def hideDownload(self):
        '''hide download due to inactivity'''
        self.hideTimer.stop()
        self.showDownload = False
        self.panel.hide()
        self.frame.hide()
        self.hideDownloadActions()
    
    def toggleDownload(self):
        '''Slot for downloadButton'''
        if self.showDownload:
            self.showDownload = False
            self.panel.hide()
            self.frame.hide()
            self.hideDownloadActions()
            self.hideTimer.stop()
        else:
            self.showDownload = True
            self.panel.show()
            self.frame.show()
            self.hideTimer.start(10000)
        
    def loadFinished(self, state):
        '''Check page url after loading to determine wether
        or not to show the reconnect and downloads button'''
        global URL
        if not state:
            URL = self.url = QFileInfo('not-open.htm').absoluteFilePath()
            self.browser.setUrl(QUrl(self.url))
        fileNameUrl = os.path.split(self.browser.url().toString())[-1]
        print(fileNameUrl)
        if fileNameUrl in self.offlinePages:
            self.reconnectButton.hide()
            self.downloadButton.hide()
            self.panel.hide()
            self.frame.hide()
            self.buttonA.hide()
            self.buttonB.hide()
            self.buttonC.hide()
            self.downloadWidget.clearSelection()
            self.showDownload = False
        else:
            self.reconnectButton.show()
            self.downloadButton.show()
            
        
    def handleUrlChange(self):
        global URL
        fullUrl = self.browser.url().toString()
        fileNameUrl = os.path.split(self.browser.url().toString())[-1]
        self.url = URL = fullUrl
        if fileNameUrl=='connecting.htm':
            for item in self.downloadItems:
                item.cancel()
            self.downloadItems.clear()
            self.downloadWidget.clear()
            connect_thread = Thread(target=connect, args=[self.browser,], daemon=True)
            connect_thread.start()
        if fullUrl == 'about:blank':
            URL = self.url = QFileInfo('index.htm').absoluteFilePath()
            self.browser.setUrl(QUrl(self.url))
        
    def updateApp(self):
        '''All timed updates here'''
        if URL != self.url:
            self.url = URL
            self.browser.setUrl(QUrl(self.url))
        if self.frame.underMouse() or self.panel.underMouse() or self.downloadButton.underMouse():
            self.hideTimer.start(10000)

    def reconnect(self):
        '''Slot for reconnectButton'''
        global URL
        self.reconnectButton.hide()
        self.downloadButton.hide()
        self.panel.hide()
        self.frame.hide()
        self.showDownload = False
        URL = self.url = QFileInfo('connecting.htm').absoluteFilePath()
        self.browser.setUrl(QUrl(self.url))
        connect_thread = Thread(target=connect, args=[self.browser,], daemon=True)
        connect_thread.start()

app = QApplication(sys.argv)
window = MainWindow()
app.exec()