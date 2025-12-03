from PyQt5 import QtWidgets, QtCore
import threading
import time


class LoadingWindow(QtWidgets.QWidget):
    def __init__(self, message="Loading, please wait..."):
        super().__init__()
        self.setWindowTitle("Loading")
        self.setFixedSize(400, 300)
        self.setStyleSheet("background-color: #282c34; color: #ffffff;")

        layout = QtWidgets.QVBoxLayout(self)

        # Add a label with a message
        self.label = QtWidgets.QLabel(message)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.label)

        # Add a progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress bar
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 2px solid #ffffff; border-radius: 5px; text-align: center; } "
            "QProgressBar::chunk { background-color: #4caf50; }"
        )
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)


class BOSbutton(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, frame, bos_estimator):
        super().__init__()
        self.frame = frame
        self.bos_estimator = bos_estimator

    def run(self):
        try:
            # Simulate board pose detection
            self.bos_estimator.board_pose_detected_set(self.frame)
            # print("Finished process button")

            # Emit the finished signal
            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))


class BOSWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, frame, bos_estimator):
        super().__init__()
        self.frame = frame
        self.bos_estimator = bos_estimator

    def run(self):
        try:
            start=time.time()
            # print("Starting BOSWorker...")
            # Start frame processing in a separate thread
            frame_thread = threading.Thread(target=self.frame.run_frame, args=(1280, 720))
            frame_thread.start()

            # Start BOS estimator thread
            self.bos_estimator.Cop_thread = threading.Thread(target=self.bos_estimator.mobbo.get_device_data)
            self.bos_estimator.Cop_thread.start()

            # Simulate board pose detection
            self.bos_estimator.board_pose_detected_set(self.frame)
            # print("Finished BOSWorker process")
            end=time.time()

            # print("the total time of execution  :",end-start)

            # Emit the finished signal
            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))


class ResetButtonProcess(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.loading_window = None
        self.worker_thread = None
        self.worker = None

    def start_worker_thread(self, frame, bos_estimator):
        """Start a new worker thread."""
        self.stop_worker_thread()  # Stop any existing thread

        # Show a new loading window
        self.loading_window = LoadingWindow("Reset Board Position, please wait...")
        self.loading_window.show()

        # Create the worker thread and worker object
        self.worker_thread = QtCore.QThread()
        self.worker = BOSbutton(frame, bos_estimator)
        self.worker.moveToThread(self.worker_thread)

        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_worker_done)
        self.worker.finished.connect(self.worker_thread.quit)  # Stop the thread's event loop
        self.worker.finished.connect(self.worker.deleteLater)  # Delete worker after finishing
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)  # Delete thread after finishing
        self.worker.error.connect(self.show_error_message)

        # Start the thread
        self.worker_thread.start()
        # print("Worker thread started.")

    def stop_worker_thread(self):
        """Stop the worker thread."""
        if self.worker_thread is not None and self.worker_thread.isRunning():
            # print("Stopping worker thread...")
            self.worker_thread.quit()  # Stop the thread's event loop
            self.worker_thread.wait()  # Wait for the thread to finish
            self.worker_thread.deleteLater()
            self.worker_thread = None
            # print("Worker thread stopped.")

    def on_worker_done(self):
        """Handle worker completion and close the loading window."""
        if self.loading_window:
            self.loading_window.close()
            self.loading_window = None  # Clean up the loading window
        # print("Worker finished and loading window closed.")

    def show_error_message(self, error_message):
        """Display error messages in a QMessageBox."""
        self.stop_worker_thread()  # Ensure the thread is stopped

        if self.loading_window:
            self.loading_window.close()  # Close the loading window
            self.loading_window = None

        # Show the error dialog
        error_box = QtWidgets.QMessageBox()
        error_box.setIcon(QtWidgets.QMessageBox.Critical)
        error_box.setWindowTitle("Error")
        error_box.setText("An error occurred:")
        error_box.setInformativeText(error_message)
        error_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        error_box.exec_()
        # print("Error displayed:", error_message)


 