#!/usr/bin/python3
import json, requests, sys, ipaddress
from pprint import pprint

url = "http://127.0.0.1/api/salt/"
key = "a46c277465919c049ecb96a468373945"

vips = ["10.120.66.21","10.120.56.14","10.120.34.17","10.120.41.17","10.120.66.17","10.121.56.14","10.121.34.17","10.121.66.17","10.121.56.22","10.121.9.23","10.121.34.19","10.121.65.22","10.121.66.21","10.121.17.35","10.121.17.65","10.120.17.35","10.120.17.36","10.121.17.62","10.120.26.35","10.121.26.35"]
grains = {}
phpipam_data = {"devices": [], "subnets": []}


try:
    with open('grains-db.json', 'r') as fp:
        grains = json.load(fp)
        print("Config loaded")
except Exception:
    print("Config file was not loaded")
    sys.exit(1)


#get sections and subnets
r = requests.get(url + 'sections/', headers={"token": key})
if r.status_code == 200:
    phpipam_data["sections"] = json.loads(r.text)["data"]
    for section in phpipam_data["sections"]:
        s = requests.get(url + "sections/" + section["id"] + "/subnets/", headers={"token": key})
        if s.status_code == 200 and s.text != "":
            phpipam_data["subnets"] += json.loads(s.text)["data"]

#get devices
r = requests.get(url + 'devices/', headers={"token": key})
if r.status_code == 200 and "data" in json.loads(r.text):
    phpipam_data["devices"] = json.loads(r.text)["data"]

for server in grains.keys():
    if len(grains[server].keys()) > 0:
        print("processing " + grains[server]["host"])
        if grains[server]["virtual"] == "physical" and "manufacturer" in grains[server]:
            serverIsNew = True
            obj_id = 0
            for device in phpipam_data["devices"]:
                if device["hostname"] == grains[server]["host"]:
                    serverIsNew = False
                    obj_id = device["id"]

            ipv4 = ""
            for ip in grains[server]["ipv4"]:
                if ip.startswith("10.120.") or ip.startswith("10.121."):
                    ipv4 = ip
                    break

            postData = {"hostname": grains[server]["host"], "custom_OS": grains[server]["osfullname"] + " " + grains[server]["osrelease"] ,"location": '1' if grains[server]["host"].startswith("RO") else '2',"custom_CPUs": grains[server]["num_cpus"],"custom_Memory": grains[server]["mem_total"], "custom_Kernel": grains[server]["kernelrelease"], "ip": ipv4}


            sections = []
            for subnet in phpipam_data["subnets"]:
                if ipaddress.ip_address(ipv4) in ipaddress.ip_network(subnet["subnet"] + '/' + subnet["mask"]):
                    sections.append(subnet["sectionId"])
            postData["sections"] = ';'.join(sections)

            print("found section " + postData["sections"])

            if "manufacturer" in grains[server]:
                postData["custom_Manufacturer"] = grains[server]["manufacturer"]
                postData["description"] = grains[server]["manufacturer"] + " " + grains[server]["productname"]
            if "productname" in grains[server]:
                postData["custom_Model"] = grains[server]["productname"]
            if "biosversion" in grains[server]:
                postData["custom_Bios"] = grains[server]["biosversion"]
                postData["custom_BiosDate"] = grains[server]["biosreleasedate"]
            if "serialnumber" in grains[server]:
                postData["custom_SerialNumber"] = grains[server]["serialnumber"]
            if "environment" in grains[server]:
                postData["custom_Environment"] = grains[server]["environment"]
            if "roles" in grains[server]:
                postData["custom_Roles"] = '\r\n'.join(grains[server]["roles"])
            if serverIsNew:
                print("add server " + grains[server]["host"])
                r = requests.post(url + 'devices/', data=json.dumps(postData), headers={"token": key, "Content-Type": "application/json"})
            elif obj_id != 0:
                print("update server " + grains[server]["host"])
                r = requests.patch(url + 'devices/' + obj_id + "/", data=json.dumps(postData), headers={"token": key, "Content-Type": "application/json"})
                print(r.text)
        for ip in grains[server]["ipv4"]:
            if ip.startswith('10.120.') or ip.startswith('10.121.'):
                postData = {}
                if "hwaddr_interfaces" in grains[server]:
                    for hwaddr in grains[server]["hwaddr_interfaces"].keys():
                        if hwaddr in ["eth0","ens160","eno1","eno49"]:
                            postData["mac"] = grains[server]["hwaddr_interfaces"][hwaddr]
                if "productname" in grains[server]:
                    postData["custom_Model"] = grains[server]["productname"]
                if "serialnumber" in grains[server]:
                    postData["custom_SerialNumber"] = grains[server]["serialnumber"]
                if "kernelrelease" in grains[server]:
                    postData["custom_Kernel"] = grains[server]["kernelrelease"]
                if "roles" in grains[server]:
                    postData["custom_Roles"] = '\r\n'.join(grains[server]["roles"])
                if "environment" in grains[server]:
                    postData["custom_Environment"] = grains[server]["environment"]
                postData.update({"ip": ip, "hostname": grains[server]["host"],"location": '1' if grains[server]["host"].startswith("RO") else '2',"custom_CPUs": grains[server]["num_cpus"],"custom_Memory": grains[server]["mem_total"]})
                if grains[server]["virtual"] != "physical" and "manufacturer" in grains[server]:
                    postData["description"] = "VM provider: " + grains[server]["manufacturer"]
                d = requests.get(url + 'devices/search/' + grains[server]["host"], headers={"token": key, "Content-Type": "application/json"})
                if json.loads(d.text)["success"] != 0:
                    postData["deviceId"] = json.loads(d.text)["data"][0]["id"]
                r = requests.get(url + 'addresses/search/' + ip, headers={"token": key})
                if json.loads(r.text)["success"] != 0:
                    del postData["ip"]
                    if ip in vips:
                        postData["description"] = "VIP"
                    r = requests.patch(url + 'addresses/' + json.loads(r.text)["data"][0]["id"] + '/', data=json.dumps(postData) ,headers={"token": key, "Content-Type": "application/json"})
                    print("update " + r.text)
                else:
                    ### find the subnet of this ip
                    for subnet in phpipam_data["subnets"]:
                        if ipaddress.ip_address(ip) in ipaddress.ip_network(subnet["subnet"] + '/' + subnet["mask"]):
                            if ip in vips:
                                postData["description"] = "VIP"
                            postData["subnetId"] = subnet["id"]
                            r = requests.post(url + 'addresses/', data=json.dumps(postData) ,headers={"token": key, "Content-Type": "application/json"})
                            print(r.text)
#pprint(phpipam_data)
