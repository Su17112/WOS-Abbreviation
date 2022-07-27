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
