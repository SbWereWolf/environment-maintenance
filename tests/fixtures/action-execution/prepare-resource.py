import pathlib,shutil,sys; pathlib.Path(sys.argv[2]).mkdir(); shutil.copy2(sys.executable,sys.argv[1])
