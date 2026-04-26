# post-genesis4
This is a PyQt5 GUI application for visualizing the output of Genesis1.3-Version4 and Genesis1.3-Version2 (experimentally supports).

### Installation
You can install with 
```shell
pip install post-genesis4
```
After installation, you can run the application with command
```shell
post-genesis4
```

### Usage

With file input box empty, `Open` button will open a file dialog to select one or more Genesis output file.
You can also input a Genesis output file path in the file input box, and then click `Open` button to load the data. 



If the output files are located on a server, you can use SSH with X11 forwarding to run the application on the server and display it on your local machine.  To do this, you can

- using terminal like `MobaXterm`
- install x11-server like `Xming` on the local machine

But it is recommended to mount the server directory to your local machine with `SFTP` using softwares like `RaiDrive` or `WinFsp`.

- RaiDrive: Add -> NAS -> SFTP



To use this application, you need to have the following dependencies installed:

- PyQt5
- h5py
- numpy
- matplotlib
- scipy
