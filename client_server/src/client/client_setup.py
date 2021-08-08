import sys
from cx_Freeze import setup, Executable

setup(
  name='client_app',
  version="0.1",
  description="Worst python socket based client-server chat, that stretches the defenition of functional",
  author="TF",
  author_email="SjasFaceMD@gmail.com",
  url="https://github.com/StrikeNeon/Chat_apps",
  executables=[Executable("main.py")]
)
