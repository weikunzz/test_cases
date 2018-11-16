from ftplib import FTP
import os,sys
import glob

#3.6.5.4
class FtpOps():
    def __init__(self,host,user,passwd):
        self.host = host
        self.user = user
        self.passwd = passwd
        try:
            self.ftp = FTP(host=self.host,user=self.user,passwd=self.passwd)
            print "========>Connect FTP Server Succuss"
            
        except Exception as ex:
            print "========>Connect Fail: ",ex

    def __enter__(self):        
        return self
    
    def get_remotepath(self,ver_name):
        folder_name  = "ICFS-"+ver_name
        self.ftp.cwd("Saturn/CQ_Release_Version")
        for i in self.ftp.nlst():
            if folder_name in i:
                self.ftp.cwd(i)
                for j in self.ftp.nlst():
                    if ".iso" in j:
                        print "========>Image Version Path: %s  ISO File Name: %s"%(i,j)                  
                        return ("/Saturn/CQ_Release_Version/"+i),j    
     
    def download(self,remotepath,f_name):
        print "========> Start Downloading: ",remotepath,f_name
        # bufsize = 1024
        self.ftp.cwd(remotepath)
        print "========> file size: ",self.ftp.size(f_name)
        f = open("AS13000-ISO/"+f_name,"wb")
        self.ftp.retrbinary('RETR ' + f_name, f.write)
        
    def __exit__(self,exc_type,exc_vaule,exc_tb):
        self.ftp.close()

def check_MD5(f_name):
    local_md5 = os.popen("md5sum AS13000/%s"%f_name).read()
    ftp_md5 = os.popen("cat AS13000-ISO/MD5.txt | grep 'linux-3.10.0.iso'").read().split(" ")[0] 
    print local_md5,ftp_md5
     
if __name__=="__main__":
    ver_name = sys.argv[1]
    iso_lst = os.popen("ls AS13000-ISO").read()
    with FtpOps("100.7.42.195","ccyf_03","000000") as ftpops:
        remotepath,f_name = ftpops.get_remotepath(ver_name)
        ftpops.download(remotepath,"MD5.txt")
        if ver_name not in iso_lst:
            print remotepath,f_name
            ftpops.download(remotepath,f_name)
            check_MD5(f_name)       
