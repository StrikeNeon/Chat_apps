import sys
from cx_Freeze import setup, Executable

build_exe_options = {"packages": ["bcrypt", "passlib"], "excludes": ["tkinter"]}
setup(
  name='server_app',
  version="0.1",
  description="Worst python socket based client-server chat, that stretches the defenition of functional",
  author="TF",
  author_email="SjasFaceMD@gmail.com",
  url="https://github.com/StrikeNeon/Chat_apps",
  options={
    "build_exe": build_exe_options
  },
  executables=[Executable("main.py")]
)
