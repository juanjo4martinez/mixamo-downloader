# Third-party modules
from PySide2 import QtCore, QtWebEngineWidgets, QtWidgets


class CustomWebPage(QtWebEngineWidgets.QWebEnginePage):
    """Custom QWebEnginePage that catches data from the JavaScript console.

    This allows us to read variables that are only stored in the browser,
    such as the 'access_token' used by Mixamo. We'll then use that token
    as an 'Authentication' header when sending HTTP Requests to its API.
    """    

    retrieved_token = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):        
        super().__init__(*args, **kwargs)

        # Reimplement the javaScriptConsoleMessage method.
        self.javaScriptConsoleMessage = self.handle_console_message

    def handle_console_message(self, level, message, lineNumber, sourceID):
        """This method decides what to do with console messages.

        :param level: Severity level a JavaScript console message can have
        :type level: QWebEnginePage.JavaScriptConsoleMessageLevel

        :param message: Message printed to the console
        :type message: str

        :param lineNumber: Line number where the message was printed
        :type lineNumber: int

        :param sourceID: Source ID
        :type sourceID: str
        """
        if "ACCESS TOKEN" in message:
            access_token = message.split(":")[-1].strip()
            self.retrieved_token.emit(access_token)
