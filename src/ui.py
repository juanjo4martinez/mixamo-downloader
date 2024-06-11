# Stdlib modules
import json

# Third-party modules
from PySide2 import QtCore, QtGui, QtWebEngineWidgets, QtWidgets

# Local modules
from downloader import HEADERS
from downloader import MixamoDownloader
from webpage import CustomWebPage


class MixamoDownloaderUI(QtWidgets.QMainWindow):
    """Main UI that allows users to bulk download animations from Mixamo.

    Users should log into their Mixamo accounts and upload the character
    they want to download animations for. This character is what Mixamo
    call the Primary Character.

    Users can choose to download all animations in Mixamo (quite slow),
    only those that contain a specific word (faster), or just the T-Pose.

    Note that only the T-Pose is downloaded with skin. Animations are
    downloaded without skin to speed things up and save space on disk.
    """
    def __init__(self):        
        """Initialize the Mixamo Downloader UI."""
        super().__init__()
        
        # Set the window title and size.
        self.setWindowTitle('Mixamo')
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QtGui.QIcon("mixamo.ico"))

        # Create a QWebEngineView instance (i.e: a web browser).
        self.browser = QtWebEngineWidgets.QWebEngineView()

        # Create an instance of our custom QWebEnginePage.
        page = CustomWebPage()
        # Set the Mixamo website as its URL.
        page.setUrl((QtCore.QUrl('https://www.mixamo.com')))
        # Apply this page to the web browser.
        self.browser.setPage(page)
        
        # The access token will be sent from the custom QWebEnginePage
        # through a signal, so we need to connect that signal to some
        # method in this class in order to get its value.
        page.retrieved_token.connect(self.apply_token)

        # Create the central widget and its layout.
        central_widget = QtWidgets.QWidget()

        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(20)

        central_widget.setLayout(layout)

        # Add the web browser to the layout.
        layout.addWidget(self.browser)

        # Add a layout for the footer (i.e: below the browser).
        footer_lyt = QtWidgets.QVBoxLayout()
        layout.addLayout(footer_lyt)

        # Add a horizontal layout to the footer.
        # This layout will contain the download options.
        anim_opt_lyt = QtWidgets.QHBoxLayout()
        footer_lyt.addLayout(anim_opt_lyt)

        # Create radio buttons for the different download options.
        self.rb_all = QtWidgets.QRadioButton("All animations")
        self.rb_all.setChecked(True)

        self.rb_query = QtWidgets.QRadioButton(
            "Animations containing the word:")

        self.le_query = QtWidgets.QLineEdit()
        self.le_query.setEnabled(False)

        self.rb_tpose = QtWidgets.QRadioButton("T-Pose (with skin)")

        # The line edit is to be enabled only when using the query option.
        self.rb_query.toggled.connect(lambda: self.le_query.setEnabled(True))
        self.rb_all.toggled.connect(lambda: self.le_query.setEnabled(False))
        self.rb_tpose.toggled.connect(lambda: self.le_query.setEnabled(False))

        # Add the radio buttons and line edit to the download options layout.
        anim_opt_lyt.addWidget(self.rb_all)
        anim_opt_lyt.addWidget(self.rb_query)
        anim_opt_lyt.addWidget(self.le_query)
        anim_opt_lyt.addWidget(self.rb_tpose)

        # Add another horizontal layout to the footer.
        # This layout will contain the Output Folder group box.
        output_dir_lyt = QtWidgets.QHBoxLayout()
        footer_lyt.addLayout(output_dir_lyt)

        # Create a group box where users can chose the output folder.
        gbox_output = QtWidgets.QGroupBox("Output Folder")
        gbox_output.setMaximumHeight(70)

        gbox_output_lyt = QtWidgets.QHBoxLayout()
        gbox_output.setLayout(gbox_output_lyt)

        # Create the content of the group box.
        self.le_path = QtWidgets.QLineEdit()
        tb_path = QtWidgets.QToolButton()

        icon = QtWidgets.QApplication.style().standardIcon(
            QtWidgets.QStyle.SP_DirIcon)

        tb_path.setIcon(icon)

        # When the tool button is clicked, launch a QFileDialog.
        tb_path.clicked.connect(self.set_path)

        # Add the line edit and tool button to the group box layout.
        gbox_output_lyt.addWidget(self.le_path)
        gbox_output_lyt.addWidget(tb_path)

        # Add the group box to its corresponding layout.
        output_dir_lyt.addWidget(gbox_output)

        # Create the button that will launch the download process.
        self.get_btn = QtWidgets.QPushButton('Start download')
        self.get_btn.clicked.connect(self.get_access_token)

        # Add the button to the footer layout.
        footer_lyt.addWidget(self.get_btn)

        # Add another horizontal layout to the footer.
        # This layout will contain the progress bar and 'Stop' button.
        prog_lyt = QtWidgets.QHBoxLayout()
        footer_lyt.addLayout(prog_lyt)

        # Create a progress bar.
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFormat(f"Downloading %v/%m")
        self.progress_bar.setAlignment(QtCore.Qt.AlignCenter)
        prog_lyt.addWidget(self.progress_bar)

        # Create a button to stop the download.
        # It will be disabled by default, and enabled only when downloading.
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_download)        
        prog_lyt.addWidget(self.stop_btn)        
        
        # Set this widget as the central one for the Main Window.
        self.setCentralWidget(central_widget)

    def get_access_token(self):
        """Enter a JavaScript command to retrieve the Mixamo access token.

        The javaScriptConsoleMessage method from QWebEnginePage will catch
        every message printed to the browser's console.

        In this case, we're printing to the console the 'access_token' used
        by Mixamo, so that the javaScriptConsoleMessage can catch it and
        return that value to us.
        """

        script = """
        var token = localStorage.getItem('access_token');
        console.log('ACCESS TOKEN:', token);
        """
        
        # Run the JavaScript code on our page.
        self.browser.page().runJavaScript(script)

    def apply_token(self, token):
        """Add the access token to the HTTP Request Headers.

        This method is invoked as soon as the access token is sent through
        the QWebEnginePage signal, so we'll use it to launch the downloader
        as well.

        :param token: Mixamo Access Token
        :type token: str
        """
        HEADERS["Authorization"] = f"Bearer {token}"
        self.run_downloader()

    def run_downloader(self):
        """Wrapper method that sets everything up for the download.

        The download is run on a separate thread to prevent the UI from
        freezing. This also allows the progress bar to the updated on
        every download, giving the user an appropriate experience.
        """
        # Create a QThread instance.
        self.thread = QtCore.QThread()

        # Get the download mode, query (if any) and the output folder path.
        mode = self.get_mode()
        query = self.le_query.text()
        path = self.le_path.text()

        # Create a MixamoDownloader instance and move it to the new thread.
        self.worker = MixamoDownloader(path, mode, query)
        self.worker.moveToThread(self.thread)

        # As soon as the thread is started, the run method on the worker
        # will be invoked so that it starts processing everything.
        self.thread.started.connect(self.worker.run)
        # The 'Stop' button will also be enabled when the thread is started.
        self.thread.started.connect(self.stop_btn.setEnabled(True))
        # The 'Download' button will be disabled.
        self.thread.started.connect(self.get_btn.setEnabled(False))

        # When the worker emits the finished signal, close the thread.
        self.worker.finished.connect(self.thread.quit)
        # Set the worker to be deleted after all pending events are done.
        self.worker.finished.connect(self.worker.deleteLater)
        # Same with the thread when it is closed.
        self.thread.finished.connect(self.thread.deleteLater)
        # Once the thread is closed, restore buttons to its default state.
        self.thread.finished.connect(lambda: self.stop_btn.setEnabled(False))
        self.thread.finished.connect(lambda: self.get_btn.setEnabled(True))

        # Read signals from the worker that allows us to set the progress bar.
        # The 'total_tasks' signal emits the amount of items to be downloaded.
        # The 'current_task' signal emits whenever an item has been downloaded.
        self.worker.total_tasks.connect(self.set_progress_bar)
        self.worker.current_task.connect(self.update_progress_bar)

        # Start the thread.
        self.thread.start()

    def set_progress_bar(self, total_tasks):
        """Set the progress bar range to the proper values.

        The 'total_tasks' signal from the QWebEnginePage emits the amount of
        animations to be downloaded. This number is what we catch with this
        method in order to set the progress bar.
        """
        # Reset the progress bar.
        self.progress_bar.reset()
        # Set the progress bar range to the proper values.
        # If we're downloading just one animation, the range will be [0, 1].
        self.progress_bar.setRange(0, total_tasks)

    def update_progress_bar(self, step):
        """Update the progress bar value.

        The 'current_task' signal from the QWebEnginePage emits every time
        an animation has been downloaded, so we'll use that value to update
        the progress bar.
        """
        self.progress_bar.setValue(step)

    def stop_download(self):
        """Send a flag to the worker to let him know that it should stop.

        Note that once the flag is sent, the code will wait for the current
        download to finish before the thread is closed.
        """
        self.worker.stop = True

    def set_path(self):
        """Ask the user to select the output folder through a QFileDialog."""
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select the output folder')
        
        # If a folder has been selected by the user, update the line edit.
        if path:
            self.le_path.setText(path)

    def get_mode(self):
        """Read the radio buttons to know which download mode to be used.

        :return: Download mode
        :rtype: str
        """
        if self.rb_all.isChecked():
            return "all"
        elif self.rb_query.isChecked():
            return "query"
        elif self.rb_tpose.isChecked():
            return "tpose"
