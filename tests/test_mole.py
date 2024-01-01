import os.path
import unittest
import pandas as pd
from ong_mole import test_config
from ong_mole.mole import Mole


class TestMole(unittest.TestCase):

    def setUp(self):
        self.test_set = test_config("test_set")
        self.mole = Mole()

    def test_100_get_token(self):
        """Tests that a token can be obtained and is valid"""
        tk = self.mole.get_jwt_token()
        self.assertTrue(self.mole.is_jwt_token_valid(),
                        "Could not get a valid mole token")

    def test_200_download_pandas(self):
        """Tests that a pandas dataframe can be downloaded"""
        df = self.mole.download_df(self.test_set)
        self.assertFalse(df.empty,
                         "Could not download a pandas dataframe")

    def test_210_download_pandas_non_existent(self):
        """Tests that exception is raised when trying to download a non-existing set"""
        non_existing_set = "asdfaasdfifaldfasdkfas"
        with self.assertRaises(ValueError) as ar:
            df = self.mole.download_df(non_existing_set)

    def test_300_download_file(self):
        """Downloads to a file and tests that content is the same as with pandas"""
        file = self.mole.download_file(self.test_set)
        df = self.mole.download_df(self.test_set)
        file_df = pd.read_excel(file, header=1)
        self.assertIsNotNone(file)
        self.assertTrue(os.path.isfile(file))
        self.assertTrue(df.equals(file_df),
                        "Dataframe and file downloads differ")
        os.remove(file)


if __name__ == '__main__':
    unittest.main()
