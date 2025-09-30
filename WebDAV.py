import xml.etree.ElementTree as ET
import datetime
import requests
import time
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class WebDAVClient:
    def __init__(self, url, username, password):
        self.url = url  # WebDAV 服务器 URL
        self.username = username  # 用户名
        self.password = password  # 密码
       # 定义时间字符串的格式
        self.time_format = "%a, %d %b %Y %H:%M:%S GMT"
        self.last_sync_time = "last_sync_time.txt"  # 用于存储上次同步时间的文件


    def _format(self,time_str):
        """将远程修改时间转换为时间戳"""
        return  time.mktime(time.strptime(time_str, self.time_format))

    def get_last_sync_time(self):
        """读取上次同步的时间"""
        if os.path.exists(self.last_sync_time):
            with open(self.last_sync_time, 'r') as file:
                return float(file.read().strip())
        return 0.0  # 如果没有记录上次同步时间，则默认返回0

    def set_last_sync_time(self):
        """记录当前时间作为上次同步时间"""
        with open(self.last_sync_time, 'w') as file:
            file.write(str(time.time()))

    def _make_request(self, method, path, data=None, headers=None):
        """通用方法，发送请求"""
        full_url = self.url + path
        try:
            response = requests.request(
                method,
                full_url,
                data=data,
                headers=headers,
                auth=(self.username, self.password)  # 使用基本认证
            )
            return response
        except requests.exceptions.RequestException as e:
            print(f"请求出错: {e}")
            return None

    def upload(self, local_file, remote_path):
        """上传文件"""
        with open(local_file, 'rb') as f:
            response = self._make_request('PUT', remote_path, data=f)
        
        if response and response.status_code == 201 or response.status_code == 204:
            print(f"文件上传成功: {local_file} -> {remote_path}")
        else:
            print(f"上传失败: {response.status_code if response else response.text} {response.text}")


    def download(self, remote_path, local_file):
        """下载文件"""
        response = self._make_request('GET', remote_path)
        
        if response and response.status_code == 200:
            with open(local_file, 'wb') as f:
                f.write(response.content)
            print(f"文件下载成功: {remote_path} -> {local_file}")
        else:
            print(f"下载失败: {response.status_code if response else response.text}")

    def list_directory(self, remote_path):
        """列出目录内容，并格式化输出"""
        propfind_xml = """<?xml version="1.0" encoding="utf-8" ?>
<propfind xmlns="DAV:">
    <allprop/>
</propfind>
"""
        headers = {'Content-Type': 'application/xml'}
        response = self._make_request('PROPFIND', remote_path, data=propfind_xml, headers=headers)
        
        file_list = []
        if response and response.status_code == 207:
            # 解析返回的 XML 内容
            root = ET.fromstring(response.text)
            # print(response.text)
            # 遍历所有的文件或目录
            for response_element in root.findall('{DAV:}response'):
                
                href = response_element.find('{DAV:}href').text
                display_name = response_element.find('{DAV:}propstat/{DAV:}prop/{DAV:}displayname')
                content_length = response_element.find('{DAV:}propstat/{DAV:}prop/{DAV:}getcontentlength')
                getcontent_type = response_element.find('{DAV:}propstat/{DAV:}prop/{DAV:}getcontenttype')
                last_modified = response_element.find('{DAV:}propstat/{DAV:}prop/{DAV:}getlastmodified')

                # 获取显示名称和最后修改时间（如果存在）
                display_name_text = display_name.text if display_name is not None else "无名称"
                last_modified_text = last_modified.text if last_modified is not None else "无信息"
                content_length_text = content_length.text if content_length is not None else "无大小"
                getcontent_type_text = getcontent_type.text if getcontent_type is not None else "无类型"
                # # 格式化输出目录内容
                print(f"路径: {href}")
                print(f"名称: {display_name_text}")
                print(f"大小: {content_length_text}")
                print(f"类型: {getcontent_type_text}")
                print(f"最后修改时间: {last_modified_text}")
                print("-" * 50)
                
                file_list.append({'href': href, 'file_name':display_name_text,'content_length':content_length_text,'getcontent_type':getcontent_type_text,'modified': last_modified_text})
            return file_list
        else:
            print(f"列出目录失败: {response.status_code if response else response.text}")

    def delete(self, remote_path):
        """删除文件"""
        response = self._make_request('DELETE', remote_path)
        
        if response and response.status_code == 204:
            print(f"文件删除成功: {remote_path}")
        else:
            print(f"删除失败: {response.status_code if response else response.text}")

    def create_directory(self, remote_path):
        """创建目录"""
        response = self._make_request('MKCOL', remote_path)
        
        if response and response.status_code == 201:
            print(f"目录创建成功: {remote_path}")
        else:
            print(f"创建目录失败: {response.status_code if response else response.text}")

    def local_aync(self,local_directory,remote_directory):
        """本地同步"""
        local_file_list = os.listdir(local_directory)
        remote_file_info = self.list_directory(remote_directory)
        remote_file_list = [i.get('file_name') for i in remote_file_info]
        need_download = list(set(remote_file_list)-set(local_file_list))
        for filename in need_download:
            file_path = self.path(filename,local_directory,remote_directory)
            self.download(file_path.get('remote_file'),file_path.get('local_file'))

    def remote_aync(self,local_directory,remote_directory):
        """远程同步"""
        local_file_list = os.listdir(local_directory)
        remote_file_info = self.list_directory(remote_directory)
        remote_file_list = [i.get('file_name') for i in remote_file_info]
        need_upload = list(set(local_file_list)-set(remote_file_list))
        for filename in need_upload:
            file_path = self.path(filename,local_directory,remote_directory)
            self.upload(file_path.get('remote_file'),file_path.get('local_file'))
    
    def path(self,filename,local_directory,remote_directory):
        """获取文件路径"""
        local_file = os.path.join(local_directory, filename)
        remote_file = os.path.join(remote_directory, filename)
        local_file = Path(local_file).as_posix()
        remote_file = Path(remote_file).as_posix()
        print({filename:{'local_file':local_file,'remote_file':remote_file}})
        return {'local_file':local_file,'remote_file':remote_file}
    
    # 增量同步示例
    def sync_files(self, local_directory, remote_directory):
        """同步本地和远程文件夹（增量同步）"""
        last_sync_time = self.get_last_sync_time()

        try:
            # 检查文件是否修改过（增量同步）
            remote_file_list = self.list_directory(remote_directory)
            for filename in os.listdir(local_directory):
                local_file = os.path.join(local_directory, filename)
                remote_file = os.path.join(remote_directory, filename)
                local_file = Path(local_file).as_posix()
                remote_file = Path(remote_file).as_posix()
                
                # 检查文件是否修改过（增量同步）
                if os.path.getmtime(local_file) > last_sync_time:
                    print(os.path.getmtime(local_file) , last_sync_time,os.path.getmtime(local_file) > last_sync_time)
                    self.upload(local_file, remote_file)

                # for remote_file_info in remote_file_list:
                #     filename = remote_file_info.get('href')[path_split:]
                #     if filename == remote_file:
                #         remote_file_mtime = remote_file_info['modified']
                # 将 remote_file_list 转换为字典，以 href 为键
                file_dict = {file['file_name']: file for file in remote_file_list}
                # 获取 /dav/Memo/a.py 的 modified 值
                remote_file_mtime = file_dict.get(filename, {}).get('modified', None)
                
                # 将远程修改时间转换为时间戳
                remote_mtime_timestamp = self._format(remote_file_mtime)
                if remote_mtime_timestamp > last_sync_time:
                    self.download(remote_file, local_file)

        except Exception as e:
            print(f"获取远程文件信息失败: {e}")
            # logging.error(f"获取远程文件信息失败: {e}")
        # 更新上次同步时间
        self.set_last_sync_time()


# 设置日志，指定编码为 'utf-8'
logging.basicConfig(
    filename='webdav_sync.log',  # 日志文件名
    level=logging.INFO,  # 日志级别
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式
    encoding='utf-8'  # 指定文件编码为 UTF-8
)

# 示例用法：
if __name__ == "__main__":
#     # WebDAV 服务器的 URL 和认证信息
    WEBDAV_URL = os.getenv('WEBDAV_URL')
    DAV_USERNAME = os.getenv('DAV_USERNAME')
    DAV_PASSWORD = os.getenv('DAV_PASSWORD')
    LOCAL_DIRECTORY = os.getenv('LOCAL_DIRECTORY')
    REMOTE_DIRECTORY = os.getenv('REMOTE_DIRECTORY')
    print(WEBDAV_URL,DAV_USERNAME,DAV_PASSWORD,LOCAL_DIRECTORY,REMOTE_DIRECTORY)
    # 初始化 WebDAV 客户端
    client = WebDAVClient(WEBDAV_URL, DAV_USERNAME, DAV_PASSWORD)
    
    # 执行增量同步
    # client.sync_files(LOCAL_DIRECTORY, REMOTE_DIRECTORY)
    # client.local_aync(LOCAL_DIRECTORY, REMOTE_DIRECTORY)
    client.sync_files(LOCAL_DIRECTORY, REMOTE_DIRECTORY)

    # print(client.list_directory(REMOTE_DIRECTORY))
    # file_list = client.list_directory("Memo")


    # # 示例：上传文件
    # client.upload("favicon.ico", "Memo/favicon.ico")

    # # 示例：下载文件
    # client.download("Memo/test.txt", "static/test.txt")  

    # # 示例：列出目录
    # client.list_directory("/remote/path/to/directory/")

    # # 示例：删除文件
    # client.delete("/remote/path/to/file_to_delete.txt")

    # # 示例：创建目录
    # client.create_directory("/remote/path/to/new_directory/")


