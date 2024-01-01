"""Needs websocket-client"""
from __future__ import annotations

import json
import os
import re
import pprint
from time import sleep
from urllib.parse import urlparse

import pandas as pd
import requests
from ong_utils import decode_jwt_token, decode_jwt_token_expiry, InternalStorage
from requests.adapters import HTTPAdapter, Retry
from websocket import create_connection

from ong_mole import server, logger
from ong_mole.selenium_mole import get_token


class Mole:

    def __init__(self, jwt_token: str = None):
        """Creates a Mole instance. It can receive a valid jwt_token, otherwise gets one from cache or opens mole
        website for the user to open"""
        self.internal_storage = InternalStorage(self.__class__.__name__)
        self.ws = None
        self.username = os.environ.get('USERNAME', os.environ.get("USER"))
        self.jwt_token = jwt_token or self.get_token_cache()
        self.server = server
        if not self.is_jwt_token_valid():
            tk = self.get_jwt_token()
            logger.info(f"Obtained token: {tk}")
        else:
            logger.info("Reusing token from cache")
        try:
            self.set_token_cache()
        except:
            logger.warning("Token could not be stored in keyring")
        self.auth_header = {"Authorization": f"Bearer {self.jwt_token}"}
        self.execution_uuid = None
        self.session = requests.Session()
        # Add retries to session object
        retries = Retry(
            total=3,
            backoff_factor=0.1,
            # status_forcelist=[502, 503, 504],
            allowed_methods={'POST', "GET"},
            # allowed_methods=None,   # Any method. POST is not included by default
        )
        scheme = urlparse(self.server).scheme
        self.session.mount(f'{scheme}://', HTTPAdapter(max_retries=retries))
        self.session.headers.update(self.auth_header)
        self.set_id = None

    def is_jwt_token_valid(self, minutes_validity=1) -> bool:
        """
        Returns true if token is valid (expires in more than given minutes in the future)
        :param minutes_validity: number of minumum minutes of validity of the token, defaults to 1
        :return: True if valid, False otherwise
        """
        if not self.jwt_token:
            return False
        try:
            decoded = decode_jwt_token(self.jwt_token)
            expiry = decode_jwt_token_expiry(self.jwt_token)
            user = decoded['sub']
            logger.debug(f"Token for {user} expires {expiry}")
            if expiry > (pd.Timestamp.now() + pd.offsets.Minute(1)):
                return True
            return False
        except:
            return False

    def get_jwt_token(self) -> str:
        """Uses selenium to interactively get a new jwt token, and stores it in internal storage. Returns the token"""
        self.jwt_token = get_token()
        if self.jwt_token is None:
            error = ValueError("Could not get token")
            logger.error(error)
            raise error
        if self.jwt_token:
            self.internal_storage.store_value(self.username, self.jwt_token)
        return self.jwt_token

    def get_token_cache(self) -> str | None:
        """Refreshes jwt token from keyring"""
        try:
            token = self.internal_storage.get_value(self.username)
        except:
            # Probably tokens where stored with a different version of library, ignore it
            return None
        return token

    def set_token_cache(self):
        """Stores self.jwt_token in keyring"""
        self.internal_storage.store_value(self.username, self.jwt_token)

    def request(self, url: str, method="get", params=None, data=None) -> dict:
        """Executes a request using the internal requests.Session object"""
        response = self.session.request(method=method, url=url, params=params,
                                        json=data)
        try:
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error: {e}")
            logger.info(f"Info on error: {response.text}")
            exit(-1)
        return response.json()

    def __del__(self):
        if self.ws:
            self.ws.close()

    def init_execution(self):
        """Inits execution id, using websocket"""
        params = {
            'negotiateVersion': '1',
        }
        js_negotiate = self.request(self.get_url("/wns/negotiate"), params=params, method="post")
        connection_token = js_negotiate['connectionToken']
        access_token = self.jwt_token

        params = {
            'id': connection_token,
            'access_token': access_token,
        }

        params = "&".join(f"{k}={v}" for k, v, in params.items())
        # print(params)
        url = self.get_url(endpoint=f"/wns?{params}", protocol="ws")

        self.ws = create_connection(url)
        for msg in [
            "{\"protocol\":\"json\",\"version\":1}\u001e{\"arguments\":[\"Mole\",\"{}\"],\"invocationId\":\"0\",\"target\":\"InitAsync\",\"type\":1}\u001e"]:
            logger.debug(f"Sending '{msg}'...")
            self.ws.send(msg)
            result = self.ws.recv()
            logger.debug("Received '%s'" % result)
            result = self.ws.recv()
            logger.debug("Received '%s'" % result)
            session_result = self.ws.recv()
            json_session = json.loads(session_result.split()[0])
            session_id = json_session['arguments'][0]
            logger.debug("Received '%s'" % json_session)
            sleep(0.1)  # To minimize potential server errors
        # Don't close websocket, just in case!
        # ws.close()
        self.execution_uuid = session_id.replace("-", "")
        return self.execution_uuid

    @property
    def execution_id(self) -> str:
        return self.execution_uuid.replace("-", "")

    @property
    def execution_url(self) -> str:
        retval = self.get_url(f"/Irion/execution/{self.execution_id}")
        return retval

    def get_url(self, endpoint: str, protocol: str = None) -> str:
        """Gets url, based in self.server potentially changing its protocol. E.g. by using ws:// instead of https://"""
        if protocol is None:
            server = self.server
        else:
            server = protocol + self.server[self.server.find(":"):]
        return server + endpoint

    def query_execution(self, extra_endpoint: str, print_output: bool = False, fresh: bool = False, **kwargs) -> dict:
        """Executes a request to the mole server"""
        url = self.execution_url + extra_endpoint
        if not fresh:
            r = self.request(url, **kwargs)
        else:
            r = requests.get(url, headers=self.auth_header)
            r.raise_for_status()
            r = r.json()
        if print_output:
            logger.info(f"Executed request to {extra_endpoint} with response: {r}")
            # pprint.pprint(r)
        return r

    def get_set_list(self) -> list:
        """Get the list of set ids from mole"""
        # This code initializes session_id
        self.query_execution("/_Layouts?$take=1", fresh=True)
        self.query_execution("/ShowErrorModal?$count=true&$distinct=false&$skip=0")
        self.query_execution("/MOLECss?$count=true&$distinct=false&$skip=0")
        # This code returns username
        self.query_execution("/Header?$count=true&$distinct=false&$skip=0")
        # print(r2)
        # Gets id_sets
        r_sets = self.query_execution("/SetSelection?$count=true&$distinct=false&$skip=0")
        id_sets = r_sets['value']
        return id_sets

    def get_set_id(self, set_name: str) -> dict | None:
        """Gets first set (as json) set that has given set_name"""
        sets = self.get_set_list()
        names = [s['SetName'] for s in sets]
        if set_name not in names:
            error = ValueError(f"Set name {set_name} not found in mole. Available sets: {', '.join(names)}")
            logger.error(error)
            raise error
        # print(id_sets)
        for set in sets:
            if set['SetName'] == set_name:
                self.set_id = set['IdSet']
                return set

    def _download_request(self) -> requests.Response:
        """Downloads self.set_id and returns request object"""
        # First: clear products. Might not be necessary...but just in case...
        self.query_execution(
            "/SetProducts?$count=true&$distinct=false&$skip=0&$filter=(1%20%20eq%20%200)&$orderby=OrderId%20asc",
            print_output=False
            )

        self.query_execution(
            f"/SetProducts?$count=true&$distinct=false&$skip=0&$filter=(IdSet%20%20eq%20%20{self.set_id})&$orderby=OrderId%20asc",
            print_output=True
        )
        response = self.session.request(method="post", url=self.execution_url + "/Download_Main",
                                        json={"IdSet": self.set_id})
        response.raise_for_status()
        return response

    def _download(self, set_name: str) -> requests.Response:
        """Returns the request Response object of the download of a set name. Raises value error if not found"""
        self.init_execution()
        self.get_set_id(set_name=set_name)
        response = self._download_request()
        return response

    def download_df(self, set_name: str) -> pd.DataFrame:
        """Gets the response of a set name into a pandas DataFrame. Raises value error if set_name is not found"""
        response = self._download(set_name)
        df = pd.read_excel(response.content, header=1)
        return df

    def download_file(self, set_name: str, path: str = None, filename: str = None) -> str | None:
        """
        Downloads a set from mole and saves it into a file
        :param set_name: name of the set of mole to download. Raises Value error if not found
        :param path: directory where file will be downloaded. Defaults to current directory
        :param filename: name of the file to download. Defaults to the file name that mole creates
        :return: the full path of the downloaded file or none in case of error
        """
        response = self._download(set_name)
        d = response.headers['content-disposition']
        fname = re.findall("filename=\"(.+)\"", d)[0]
        path = path or os.curdir
        filename = filename or fname
        file_path = os.path.join(path, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path
