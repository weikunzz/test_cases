import os,sys
def get_status(devtype):
     with open("./{devdir}/ip.txt".format(devdir=devtype),"r") as f:
        ips_hosts = f.readlines()
        for ip_host in ips_hosts:
            ip_host = ip_host.split(" ")
            ip = ip_host[0].strip()
            host = ip_host[-1].strip()
            #if "0% packet loss" in os.popen("ping {i} -c 2".format(i=ip)).read():
            if host in os.popen("ssh root@{i} hostname".format(i=ip)).read():
               print "====> %s %s is online"%(ip,host)
               continue
            else:
               print "====> %s %s is offline"%(ip,host)
               sys.exit(1)
if __name__=="__main__":
    devtype = sys.argv[1]
    get_status(devtype)
