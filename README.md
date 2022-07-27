近期投搞论文发现参考文献的期刊名要求使用缩写，看着一大页的参考文献直接裂开，一个个去Web of Science上查要查到什么时候去，于是乎有了想法，利用Python写了一个WOS期刊缩写的查询软件。

# 找接口
我们的最终目的就是通过期刊名来获得期刊缩写名，因此我们通过期刊缩写名一步步逆向分析请求过程。

以==SIGNAL PROCESSING==期刊为例，通过分析下面这一页的请求过程，找到了返回期刊缩写的请求。
![在这里插入图片描述](https://img-blog.csdnimg.cn/ed2384a08434486a82a55346b9914c41.png)
该请求是一个==POST==请求，请求数据如下：
![在这里插入图片描述](https://img-blog.csdnimg.cn/fee5bb336ad64893857414ebdebdfbf7.png)
其中比较重要的就是==journal==参数，而该参数是期刊的==JCR缩写==，因此我们现在的目的就是得到期刊的JCR缩写。

我们继续向上找，又找到了如下的请求：
![在这里插入图片描述](https://img-blog.csdnimg.cn/cc2f8da58db041178cfc14b53e3bff18.png)
该请求通过POST期刊的==ISSN==来获得期刊的JCR缩写：
![在这里插入图片描述](https://img-blog.csdnimg.cn/f5c5f1e19c364d96b0dbfde7f5f0d054.png)
于是现在的任务变成了获取期刊的ISSN。

但是翻遍了整个请求过程也没有找到通过期刊名获得ISSN的请求，正当一筹莫展时，突然想到我们也可以不在WOS上通过期刊名获取ISSN，一些国内的网站上也可以进行这一步，而且还比WOS快，如==LetPub==。

接下来分析==LetPub==的搜索过程，发现它发送了一个==POST==请求，返回的是一个静态页面：
![在这里插入图片描述](https://img-blog.csdnimg.cn/7379e3f2b1ad498785c941a3a685964e.png)
而==ISSN==就在这里：
![在这里插入图片描述](https://img-blog.csdnimg.cn/ad65397693d7497c9baaa9b94e7a35b3.png)

到这里，整个流程需要用到的请求过程就全部得到了。

# 利用python的requests模拟请求
首先模拟LetPub的请求，这个没什么难度，也不用考虑Cookie，代码如下：

```python
    def getISSNfromLetPub(self, journal: str) -> tuple:
        journal = journal.upper()

        url = 'http://www.letpub.com.cn/index.php?page=journalapp&view=search'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                   'Referer': 'http://www.letpub.com.cn/index.php?page=journalapp&view=search',
                   'Content-Type': 'application/x-www-form-urlencoded'}
        postData = {'searchname': journal, 'searchissn': '', 'searchfield': '', 'searchimpactlow': '', 'searchimpacthigh': '', 'searchscitype': '', 'view': 'search',
                    'searchcategory1': '', 'searchcategory2': '', 'searchjcrkind': '', 'searchopenaccess': '', 'searchsort': 'relevance'}

        html = requests.post(url, data=urlencode(postData), headers=headers)
        html = HTML(html.text)
        ISSN = html.xpath(f'//*[@id="yxyz_content"]/table[1]/tr[3]/td[1]/text()')  # ISSN
        LetPubJCR = html.xpath(f'//*[@id="yxyz_content"]/table[1]/tr[3]/td[2]/font/text()')  # LetPub JCR缩写

        return ISSN[0] if ISSN else '', LetPubJCR[0] if LetPubJCR else ''
```
该方法的返回值即是ISSN号以及LetPub上查到的缩写(这个缩写可能不准)。

下面模拟WOS的请求，这里需要考虑Cookie，代码如下：

```python
    def getWOSAbbreviation(self, ISSN: str) -> tuple:
        session = requests.session()

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                   'Referer': 'https://access.clarivate.com/'}
        # 获取cookie
        if exists('cookies.json'):
            with open('cookies.json', 'r') as f:
                cookies = load(f)
                for name in cookies:
                    session.cookies.set(name, cookies[name])
        else:
            url = 'https://www.webofscience.com/wos/alldb/basic-search'
            html = session.get(url, headers=headers)
            # print(html.text)
            with open('cookies.json', 'w') as f:
                dump(session.cookies.get_dict(), f)

        # 获取请求头x-1p-inc-sid
        url = f'https://login.incites.clarivate.com/?DestApp=IC2JCR&authCode=null&app=jcr&referrer=target%3Dhttps%3A%2F%2Fjcr.clarivate.com%2Fjcr-jp%2Fjournal-profile%3Fissn%3D{ISSN}%26'
        html = session.get(url, headers=headers)
        # print(html.text)
        cookies_sid = session.cookies.get_dict().get('PSSID', '')
        if cookies_sid == '':  # 没有获取到就直接返回四个空
            return '', '', '', ''

        # 通过ISSN获取JCR缩写
        url = f'https://jcr.clarivate.com/api/jcr3/journalprofile/v1/journal-informationByIssnEssn'
        headers['Content-Type'] = 'application/json'
        headers['Referer'] = f'https://jcr.clarivate.com/jcr-jp/journal-profile?Init=Yes&issn={ISSN}&SrcApp=IC2LS'
        headers['x-1p-inc-sid'] = cookies_sid
        postData = {'issnEissn': ISSN}
        try:
            html = requests.post(url, data=dumps(postData), headers=headers)
            data = html.json().get('data', {})
        except:
            data = {}
        abbreviatedTitle = data.get('abbreviatedTitle', '')  # WOS JCR ABBREVIATION
        issn = data.get('issn', '')  # WOS ISSN
        eissn = data.get('eissn', '')  # WOS EISSN

        # 通过JCR缩写获取ISO缩写
        url = f'https://jcr.clarivate.com/api/jcr3/journalprofile/v1/journal-information'
        headers['Referer'] = f'https://jcr.clarivate.com/jcr-jp/journal-profile?journal={abbreviatedTitle}&year=2021'.replace(' ', '%20')
        postData = {'journal': abbreviatedTitle, 'year': f'{int(strftime("%Y")) - 1}'}
        try:
            html = requests.post(url, data=dumps(postData), headers=headers)
            isoAbbreviation = html.json().get('data', {}).get('isoAbbreviation', '')  # WOS ISO ABBREVIATION
        except:
            isoAbbreviation = ''

        return issn, eissn, abbreviatedTitle, isoAbbreviation
```
首先是请求WOS的搜索页，这一步只是为了获取Cookie，并且保存为cookies.json文件，下次就直接使用这个cookie少了一步请求。

接下来尝试的是从==通过ISSN获取JCR缩写==这里开始，但是总是返回401错误。于是分析了请求头发现其中包含了一个之前没有的参数，即==x-1p-inc-sid==，而该参数恰好是Cookie里的一个字段(猜测是一种反爬措施)，其第一次出现是在第二个请求过程中，因此在请求头中添加了该字段，并发送了第二个请求。

剩下的请求过程与上面的分析相同，最后返回==ISSN，EISSN，JCR缩写，ISO缩写==四个字符串。

至此，软件的主要部分就完成了。

# UI界面
既然是为了方便，不能每次都修改代码的期刊名是吧，于是利用QtDesigner写了如下的界面：
![在这里插入图片描述](https://img-blog.csdnimg.cn/11bac2e1c1d54700955f9c2378eb734a.png)
代码如下，保存为==MainWindow.py==。

```python
# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'MainWindow.ui'
#
# Created by: PyQt5 UI code generator 5.15.4
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(630, 250)
        MainWindow.setMinimumSize(QtCore.QSize(630, 250))
        MainWindow.setMaximumSize(QtCore.QSize(630, 250))
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem, 2, 1, 1, 1)
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem1)
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setMinimumSize(QtCore.QSize(0, 30))
        self.label.setMaximumSize(QtCore.QSize(16777215, 30))
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.horizontalLayout_5.addWidget(self.label)
        self.verticalLayout.addLayout(self.horizontalLayout_5)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem2)
        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        self.label_2.setMinimumSize(QtCore.QSize(0, 30))
        self.label_2.setMaximumSize(QtCore.QSize(16777215, 30))
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_2.setFont(font)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout.addWidget(self.label_2)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem3 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem3)
        self.label_3 = QtWidgets.QLabel(self.centralwidget)
        self.label_3.setMinimumSize(QtCore.QSize(0, 30))
        self.label_3.setMaximumSize(QtCore.QSize(16777215, 30))
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_3.setFont(font)
        self.label_3.setObjectName("label_3")
        self.horizontalLayout_2.addWidget(self.label_3)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        spacerItem4 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(spacerItem4)
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setMinimumSize(QtCore.QSize(0, 30))
        self.label_4.setMaximumSize(QtCore.QSize(16777215, 30))
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_4.setFont(font)
        self.label_4.setObjectName("label_4")
        self.horizontalLayout_4.addWidget(self.label_4)
        self.verticalLayout.addLayout(self.horizontalLayout_4)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        spacerItem5 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem5)
        self.label_5 = QtWidgets.QLabel(self.centralwidget)
        self.label_5.setMinimumSize(QtCore.QSize(0, 30))
        self.label_5.setMaximumSize(QtCore.QSize(16777215, 30))
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)
        self.label_5.setFont(font)
        self.label_5.setObjectName("label_5")
        self.horizontalLayout_3.addWidget(self.label_5)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_7.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.lineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit.setMinimumSize(QtCore.QSize(400, 30))
        self.lineEdit.setMaximumSize(QtCore.QSize(400, 30))
        self.lineEdit.setObjectName("lineEdit")
        self.horizontalLayout_6.addWidget(self.lineEdit)
        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton.setMinimumSize(QtCore.QSize(0, 30))
        self.pushButton.setMaximumSize(QtCore.QSize(16777215, 30))
        font = QtGui.QFont()
        font.setFamily("宋体")
        font.setPointSize(11)
        font.setBold(True)
        font.setWeight(75)
        self.pushButton.setFont(font)
        self.pushButton.setObjectName("pushButton")
        self.horizontalLayout_6.addWidget(self.pushButton)
        self.verticalLayout_2.addLayout(self.horizontalLayout_6)
        self.lineEdit_2 = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_2.setMinimumSize(QtCore.QSize(400, 30))
        self.lineEdit_2.setMaximumSize(QtCore.QSize(400, 30))
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.verticalLayout_2.addWidget(self.lineEdit_2)
        self.lineEdit_3 = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_3.setMinimumSize(QtCore.QSize(400, 30))
        self.lineEdit_3.setMaximumSize(QtCore.QSize(400, 30))
        self.lineEdit_3.setObjectName("lineEdit_3")
        self.verticalLayout_2.addWidget(self.lineEdit_3)
        self.lineEdit_5 = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_5.setMinimumSize(QtCore.QSize(400, 30))
        self.lineEdit_5.setMaximumSize(QtCore.QSize(400, 30))
        self.lineEdit_5.setObjectName("lineEdit_5")
        self.verticalLayout_2.addWidget(self.lineEdit_5)
        self.lineEdit_4 = QtWidgets.QLineEdit(self.centralwidget)
        self.lineEdit_4.setMinimumSize(QtCore.QSize(400, 30))
        self.lineEdit_4.setMaximumSize(QtCore.QSize(400, 30))
        self.lineEdit_4.setObjectName("lineEdit_4")
        self.verticalLayout_2.addWidget(self.lineEdit_4)
        self.horizontalLayout_7.addLayout(self.verticalLayout_2)
        self.gridLayout.addLayout(self.horizontalLayout_7, 1, 1, 1, 1)
        spacerItem6 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem6, 0, 1, 1, 1)
        spacerItem7 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem7, 1, 0, 1, 1)
        spacerItem8 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem8, 1, 2, 1, 1)
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "WOS期刊缩写查询"))
        self.label.setText(_translate("MainWindow", "期刊全称："))
        self.label_2.setText(_translate("MainWindow", "ISSN："))
        self.label_3.setText(_translate("MainWindow", "EISSN："))
        self.label_4.setText(_translate("MainWindow", "JCR缩写："))
        self.label_5.setText(_translate("MainWindow", "ISO缩写："))
        self.pushButton.setText(_translate("MainWindow", "查询"))
```

# 整体代码
为了使用UI界面，在主文件(==main.py==)中继承了界面方法，并将按钮绑定了搜索函数，在搜索函数中使用上述的请求过程，来获取期刊缩写。
同时，由于WOS是国外网站，请求太慢，为了避免主线程阻塞导致界面卡顿，搜索过程利用子线程实现。且搜索时禁用按钮放置同时发送过多请求。最后利用pyinstaller工具打包成exe程序(==pyinstaller -F -w -n WOS期刊缩写查询.exe main.py==)，代码如下：
```python
from json import dumps, dump, load
from os.path import exists
from threading import Thread
from time import strftime
from urllib.parse import urlencode

import requests
from PyQt5.QtWidgets import QMainWindow, QApplication
from lxml.etree import HTML

from MainWindow import Ui_MainWindow


class MyWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.startSearch)

    def startSearch(self):
        self.pushButton.setEnabled(False)
        t = Thread(target=self.search)
        t.setDaemon(True)
        t.start()

    def search(self):
        journal = self.lineEdit.text()
        if journal:  # 如果有内容待查询
            ISSN, LetPubJCR = self.getISSNfromLetPub(journal)  # 通过LetPub获得ISSN
            if ISSN:
                issn, eissn, abbreviatedTitle, isoAbbreviation = self.getWOSAbbreviation(ISSN)  # 通过WOS获得缩写
            else:
                issn, eissn, abbreviatedTitle, isoAbbreviation = '', '', '', ''
            self.lineEdit_2.clear()
            self.lineEdit_2.setText(issn)
            self.lineEdit_3.clear()
            self.lineEdit_3.setText(eissn)
            self.lineEdit_5.clear()
            self.lineEdit_5.setText(abbreviatedTitle)
            self.lineEdit_4.clear()
            self.lineEdit_4.setText(isoAbbreviation)
        self.pushButton.setEnabled(True)

    def getISSNfromLetPub(self, journal: str) -> tuple:
        journal = journal.upper()

        url = 'http://www.letpub.com.cn/index.php?page=journalapp&view=search'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                   'Referer': 'http://www.letpub.com.cn/index.php?page=journalapp&view=search',
                   'Content-Type': 'application/x-www-form-urlencoded'}
        postData = {'searchname': journal, 'searchissn': '', 'searchfield': '', 'searchimpactlow': '', 'searchimpacthigh': '', 'searchscitype': '', 'view': 'search',
                    'searchcategory1': '', 'searchcategory2': '', 'searchjcrkind': '', 'searchopenaccess': '', 'searchsort': 'relevance'}

        html = requests.post(url, data=urlencode(postData), headers=headers)
        html = HTML(html.text)
        ISSN = html.xpath(f'//*[@id="yxyz_content"]/table[1]/tr[3]/td[1]/text()')  # ISSN
        LetPubJCR = html.xpath(f'//*[@id="yxyz_content"]/table[1]/tr[3]/td[2]/font/text()')  # LetPub JCR缩写

        return ISSN[0] if ISSN else '', LetPubJCR[0] if LetPubJCR else ''

    def getWOSAbbreviation(self, ISSN: str) -> tuple:
        session = requests.session()

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                   'Referer': 'https://access.clarivate.com/'}
        # 获取cookie
        if exists('cookies.json'):
            with open('cookies.json', 'r') as f:
                cookies = load(f)
                for name in cookies:
                    session.cookies.set(name, cookies[name])
        else:
            url = 'https://www.webofscience.com/wos/alldb/basic-search'
            html = session.get(url, headers=headers)
            # print(html.text)
            with open('cookies.json', 'w') as f:
                dump(session.cookies.get_dict(), f)

        # 获取请求头x-1p-inc-sid
        url = f'https://login.incites.clarivate.com/?DestApp=IC2JCR&authCode=null&app=jcr&referrer=target%3Dhttps%3A%2F%2Fjcr.clarivate.com%2Fjcr-jp%2Fjournal-profile%3Fissn%3D{ISSN}%26'
        html = session.get(url, headers=headers)
        # print(html.text)
        cookies_sid = session.cookies.get_dict().get('PSSID', '')
        if cookies_sid == '':  # 没有获取到就直接返回四个空
            return '', '', '', ''

        # 通过ISSN获取JCR缩写
        url = f'https://jcr.clarivate.com/api/jcr3/journalprofile/v1/journal-informationByIssnEssn'
        headers['Content-Type'] = 'application/json'
        headers['Referer'] = f'https://jcr.clarivate.com/jcr-jp/journal-profile?Init=Yes&issn={ISSN}&SrcApp=IC2LS'
        headers['x-1p-inc-sid'] = cookies_sid
        postData = {'issnEissn': ISSN}
        try:
            html = requests.post(url, data=dumps(postData), headers=headers)
            data = html.json().get('data', {})
        except:
            data = {}
        abbreviatedTitle = data.get('abbreviatedTitle', '')  # WOS JCR ABBREVIATION
        issn = data.get('issn', '')  # WOS ISSN
        eissn = data.get('eissn', '')  # WOS EISSN

        # 通过JCR缩写获取ISO缩写
        url = f'https://jcr.clarivate.com/api/jcr3/journalprofile/v1/journal-information'
        headers['Referer'] = f'https://jcr.clarivate.com/jcr-jp/journal-profile?journal={abbreviatedTitle}&year=2021'.replace(' ', '%20')
        postData = {'journal': abbreviatedTitle, 'year': f'{int(strftime("%Y")) - 1}'}
        try:
            html = requests.post(url, data=dumps(postData), headers=headers)
            isoAbbreviation = html.json().get('data', {}).get('isoAbbreviation', '')  # WOS ISO ABBREVIATION
        except:
            isoAbbreviation = ''

        return issn, eissn, abbreviatedTitle, isoAbbreviation

if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    mywindow = MyWindow()
    mywindow.show()
    sys.exit(app.exec_())
```
