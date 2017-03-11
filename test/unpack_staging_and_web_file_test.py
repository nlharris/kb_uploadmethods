# -*- coding: utf-8 -*-
import unittest
import os  # noqa: F401
import json  # noqa: F401
import time
import requests
import ftplib
import shutil
from mock import patch

from os import environ
try:
    from ConfigParser import ConfigParser  # py2
except:
    from configparser import ConfigParser  # py3

from pprint import pprint  # noqa: F401

from biokbase.workspace.client import Workspace as workspaceService
from kb_uploadmethods.kb_uploadmethodsImpl import kb_uploadmethods
from kb_uploadmethods.kb_uploadmethodsServer import MethodContext
from kb_uploadmethods.Utils.UnpackFileUtil import UnpackFileUtil
from DataFileUtil.DataFileUtilClient import DataFileUtil


class kb_uploadmethodsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.token = environ.get('KB_AUTH_TOKEN', None)
        cls.user_id = requests.post(
            'https://kbase.us/services/authorization/Sessions/Login',
            data='token={}&fields=user_id'.format(cls.token)).json()['user_id']
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': cls.token,
                        'user_id': cls.user_id,
                        'provenance': [
                            {'service': 'kb_uploadmethods',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('kb_uploadmethods'):
            cls.cfg[nameval[0]] = nameval[1]
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = workspaceService(cls.wsURL, token=cls.token)
        cls.serviceImpl = kb_uploadmethods(cls.cfg)
        cls.dfu = DataFileUtil(os.environ['SDK_CALLBACK_URL'], token=cls.token)
        cls.scratch = cls.cfg['scratch']
        cls.shockURL = cls.cfg['shock-url']

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    @classmethod
    def make_ref(self, objinfo):
        return str(objinfo[6]) + '/' + str(objinfo[0]) + '/' + str(objinfo[4])

    @classmethod
    def delete_shock_node(cls, node_id):
        header = {'Authorization': 'Oauth {0}'.format(cls.token)}
        requests.delete(cls.shockURL + '/node/' + node_id, headers=header,
                        allow_redirects=True)
        print('Deleted shock node ' + node_id)

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        if hasattr(self.__class__, 'wsName'):
            return self.__class__.wsName
        suffix = int(time.time() * 1000)
        wsName = "test_kb_uploadmethods_" + str(suffix)
        ret = self.getWsClient().create_workspace({'workspace': wsName})  # noqa
        self.__class__.wsName = wsName
        return wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def mock_file_to_staging(file_path_list, subdir_folder=None):
        print 'Mocking _file_to_staging'
        print "Mocking uploaded files to staging area:\n{}".format('\n'.join(file_path_list))

    def mock_download_staging_file(params):
        print 'Mocking DataFileUtilClient.download_staging_file'
        print params

        fq_filename = params.get('staging_file_subdir_path')
        fq_path = os.path.join('/kb/module/work/tmp', fq_filename)
        shutil.copy(os.path.join("data", fq_filename), fq_path)

        return {'copy_file_path': fq_path}

    @patch.object(UnpackFileUtil, "_file_to_staging", side_effect=mock_file_to_staging)
    def test_unpack_web_file_direct_download_trailing_space(self, _file_to_staging):
        file_url = 'https://anl.box.com/shared/static/'
        file_url += 'g0064wasgaoi3sax4os06paoyxay4l3r.zip   '

        params = {
            'download_type': 'Direct Download',
            'file_url': file_url,
            'workspace_name': self.getWsName()
        }

        ref = self.getImpl().unpack_web_file(self.getContext(), params)
        self.assertTrue('unpacked_file_path' in ref[0])
        self.assertTrue('report_ref' in ref[0])
        self.assertTrue('report_name' in ref[0])
        self.assertEqual(6, len(ref[0].get('unpacked_file_path').split(',')))
        for file_path in ref[0].get('unpacked_file_path').split(','):
            self.assertRegexpMatches(
                                os.path.basename(file_path),
                                'file[1-6]\.txt')

    @patch.object(UnpackFileUtil, "_file_to_staging", side_effect=mock_file_to_staging)
    def test_unpack_web_file_direct_download_multiple_urls(self, _file_to_staging):
        file_url = '  https://anl.box.com/shared/static/'
        file_url += 'g0064wasgaoi3sax4os06paoyxay4l3r.zip'
        params = {
          'download_type': 'Direct Download',
          'workspace_name': self.getWsName(),
          'urls_to_add_web_unpack': [
            {
                'file_url': file_url
            },
            {
                'file_url': file_url
            }
          ]
        }

        ref = self.getImpl().unpack_web_file(self.getContext(), params)
        self.assertTrue('unpacked_file_path' in ref[0])
        self.assertTrue('report_ref' in ref[0])
        self.assertTrue('report_name' in ref[0])
        self.assertEqual(12, len(ref[0].get('unpacked_file_path').split(',')))
        for file_path in ref[0].get('unpacked_file_path').split(','):
            self.assertRegexpMatches(
                            os.path.basename(file_path),
                            'file[1-6]\.txt')

    @patch.object(UnpackFileUtil, "_file_to_staging", side_effect=mock_file_to_staging)
    def test_unpack_web_file_dropbox(self, _file_to_staging):
        params = {
            'download_type': 'DropBox',
            'file_url': 'https://www.dropbox.com/s/cbiywh2aihjxdf5/Archive.zip?dl=0',
            'workspace_name': self.getWsName()
        }

        ref = self.getImpl().unpack_web_file(self.getContext(), params)
        self.assertTrue('unpacked_file_path' in ref[0])
        self.assertTrue('report_ref' in ref[0])
        self.assertTrue('report_name' in ref[0])
        self.assertEqual(6, len(ref[0].get('unpacked_file_path').split(',')))
        for file_path in ref[0].get('unpacked_file_path').split(','):
            self.assertRegexpMatches(
                                os.path.basename(file_path),
                                'file[1-6]\.txt')

    @patch.object(UnpackFileUtil, "_file_to_staging", side_effect=mock_file_to_staging)
    def test_unpack_web_file_ftp(self, _file_to_staging):
        # copy test file to FTP
        fq_filename = "Archive.zip"
        ftp_connection = ftplib.FTP('ftp.uconn.edu')
        ftp_connection.login('anonymous', 'anonymous@domain.com')
        ftp_connection.cwd("/48_hour/")

        if fq_filename not in ftp_connection.nlst():
            fh = open(os.path.join("data", fq_filename), 'rb')
            ftp_connection.storbinary('STOR Archive.zip', fh)
            fh.close()

        params = {
            'download_type': 'FTP',
            'file_url': 'ftp://ftp.uconn.edu/48_hour/Archive.zip   ',
            'workspace_name': self.getWsName()
        }

        ref = self.getImpl().unpack_web_file(self.getContext(), params)
        self.assertTrue('unpacked_file_path' in ref[0])
        self.assertTrue('report_ref' in ref[0])
        self.assertTrue('report_name' in ref[0])
        self.assertEqual(6, len(ref[0].get('unpacked_file_path').split(',')))
        for file_path in ref[0].get('unpacked_file_path').split(','):
            self.assertRegexpMatches(
                        os.path.basename(file_path),
                        'file[1-6]\.txt')

    @patch.object(UnpackFileUtil, "_file_to_staging", side_effect=mock_file_to_staging)
    def test_unpack_web_file_google_drive(self, _file_to_staging):
        file_url = 'https://drive.google.com/open?id=0B0exSa7ebQ0qSlJiWEVWYU5rYWM'
        params = {
            'download_type': 'Google Drive',
            'file_url': file_url,
            'workspace_name': self.getWsName()
        }

        ref = self.getImpl().unpack_web_file(self.getContext(), params)
        self.assertTrue('unpacked_file_path' in ref[0])
        self.assertTrue('report_ref' in ref[0])
        self.assertTrue('report_name' in ref[0])
        self.assertEqual(6, len(ref[0].get('unpacked_file_path').split(',')))
        for file_path in ref[0].get('unpacked_file_path').split(','):
            self.assertRegexpMatches(
                            os.path.basename(file_path),
                            'file[1-6]\.txt')

    @patch.object(DataFileUtil, "download_staging_file", side_effect=mock_download_staging_file)
    @patch.object(UnpackFileUtil, "_file_to_staging", side_effect=mock_file_to_staging)
    def test_unpack_staging_file(self, _file_to_staging, download_staging_file):
        params = {
          'staging_file_subdir_path': 'Archive.zip',
          'workspace_name': self.getWsName()
        }

        ref = self.getImpl().unpack_staging_file(self.getContext(), params)
        self.assertTrue('unpacked_file_path' in ref[0])
        self.assertTrue('report_ref' in ref[0])
        self.assertTrue('report_name' in ref[0])
        self.assertEqual(6, len(ref[0].get('unpacked_file_path').split(',')))
        for file_path in ref[0].get('unpacked_file_path').split(','):
            self.assertRegexpMatches(
                        os.path.basename(file_path),
                        'file[1-6]\.txt')
