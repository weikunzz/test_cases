import requests
from bs4 import BeautifulSoup
import dateime
import re
import json

def getNewsDestil(newsurl):
	result = {}
	res = requests.get(newsurl)
	res.encoding = 'utf-8'
	soup = BeautifulSoup(res.text,'html.parser')
	result['title'] = soup.select('#artibodyTile')[0].text
	result['newssource'] = soup.select('.time-source span a')[0].text
	timesource = soup.select('.time-source')[0].contents[0].strip()
	result['dt'] = datetime.strptime(timesource,'%Y%m%d%H:%M')
	result['article'] = ''.join([p.text.strip() for p in soup.select('#artibody p')[:-1]])
	result['editor'] = soup.select('.article-editor')[0].text.strip('责任编辑 :')
	result['comments'] = getCommentCount(newsurl)
	return result

def getCommentCount(newsurl):
	m = re.search('doc-i(.*).shtml',newsurl)
	newsid = m.group(1)
	comments = requests.get(commentURL.format(newsid))
	jd = json.load(comments.text.strip('var data=')
	return jd['result']['count']['total']
	