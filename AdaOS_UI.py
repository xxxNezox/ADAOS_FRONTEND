import requests
import customtkinter as ctk
from tkinter import filedialog, END
from flask import Flask, request, jsonify
import wave
import pyaudio
import queue
import os
import json
import base64
from PIL import Image
import threading
import subprocess
import ast
from dotenv import load_dotenv, set_key

load_dotenv()

from sandbox.code import CodeTool
from sandbox.tool_result import ToolResult
#----------------------------Отдел Окна----------------------------#

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.base_api_url = "http://127.0.0.1:8000/api"
        self.init_user_url = f"{self.base_api_url}/init_user"
        self.text_target_url = f"{self.base_api_url}/text"
        self.audio_target_url = f"{self.base_api_url}/transcribe"
        self.user_id = os.getenv('USER_ID')

        self.code_tool = CodeTool()

        self.title("Rasa Chat App")
        self.geometry("400x600")
        self.minsize(400,600)

        self.recording = False

        self.chat_frame = ctk.CTkScrollableFrame(self, width=380, height=500)
        self.chat_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.chat_frame._scrollbar.grid_remove()

        self.chat_frame.grid_columnconfigure(0, weight=1)

        self.input_frame = ctk.CTkFrame(self, height = 40)
        self.input_frame.pack(side="left", fill="both", expand = True, padx = 10, pady = 5)
        
        self.entry_text = ctk.CTkEntry(self.input_frame, fg_color= "transparent", border_width = 0, placeholder_text="Введите сообщение...")
        self.entry_text.pack(side = "left", fill = "x", expand = True, padx = 5, pady = 5)
        self.entry_text.bind("<Return>", self.send_message)

        self.send_icon = ctk.CTkImage(light_image=Image.open("Images/up-arrow.png"), size=(15,15))
        self.send_button = ctk.CTkButton(self.input_frame, text="", image = self.send_icon, width = 30, command= self.send_message)
        self.send_button.pack(side = "right", expand = False, padx =(5, 5), pady = 5)

        self.record_icon = ctk.CTkImage(light_image=Image.open("Images/microphone.png"), size=(15,15))
        self.record_button = ctk.CTkButton(self.input_frame, text="", image = self.record_icon, width = 30)
        self.record_button.pack(side = "right", expand = False, padx=(2, 0), pady = 5)
        self.record_button.bind("<ButtonPress-1>", self.start_recording)
        self.record_button.bind("<ButtonRelease-1>", self.stop_recording)

        self.message_queue = queue.Queue()

        self.grid_counter = 0
        
        self.update_RASA_message()

        self.init_user_id()

    #----------------------------Отдел Обновления сообщений----------------------------#

    # Обновить сообщение Расы
    def update_RASA_message(self):

        while not self.message_queue.empty():

            message = self.message_queue.get()

            self.text_widget = ctk.CTkTextbox(self.chat_frame, width=220, height=16, wrap="word")

            self.text_widget.grid(row=self.grid_counter, column=0, sticky = 'w', pady = 5)
            self.grid_counter += 1

            self.text_widget.insert("1.0",f"Раса\n{message}")

            self.adjust_text_height()

            self.text_widget.configure(height = self.new_height, state = "disabled")

        self.chat_frame.after(100, self.update_RASA_message)

    # Обновить сообщение пользователя
    def update_User_message(self, message):

        self.text_widget = ctk.CTkTextbox(self.chat_frame, fg_color="green", width=220, height=16, wrap="word")
        self.text_widget.grid(row=self.grid_counter, column=0, sticky = 'e', padx = 5, pady = 5)
        self.grid_counter += 1
        
        self.text_widget.insert("1.0",f"Пользователь\n{message}")

        self.adjust_text_height()

        self.text_widget.configure(height = self.new_height, state = "disabled")

    # Изменение высоты текста
    def adjust_text_height(self):

        text = self.text_widget.get("2.0", "end")
        num_char = len(text) - 1

        if num_char % 30 == 0:
            rows = (num_char // 30) - 1
        else:
            rows = (num_char // 30)
        self.new_height = 52 + rows * 18

        return self.new_height

    #----------------------------Отдел Записи Голоса----------------------------#

    # Записать голосового сообщения
    def record_and_save_audio(self):
        
        print("record started....")

        audio = pyaudio.PyAudio()

        stream = audio.open(format = pyaudio.paInt16, channels = 1, rate = 44100, input = True, frames_per_buffer = 1024)

        frames = []

        while self.recording:
            data = stream.read(1024)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        audio.terminate()

        with wave.open("record.wav", "wb") as sound_file:
            sound_file.setnchannels(1)
            sound_file.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
            sound_file.setframerate(44100)
            sound_file.writeframes(b''.join(frames))
        
        self.send_audio()
        
    # Начать запись
    def start_recording(self, event):
        if not self.recording:
            self.recording = True
            self.record_thread = threading.Thread(target = self.record_and_save_audio, daemon = True)
            self.record_thread.start()

    # Остановить запись
    def stop_recording(self, event):
        self.recording = False
    
    # Отправить аудио
    def send_audio(self):

        try:
            with open("record.wav", "rb") as file:
                file_data = file.read()
    
            # files = {"file": ("record.wav", file_data, "audio/mpeg")}
            # response = requests.post(self.audio_target_url, json = {"user_id" : self.user_id, "file": files})

            files = {
                'user_id': (None, str(self.user_id)),  # Form field
                'file': ("record.wav", file_data, 'audio/wav')  # File field
            }

            response = requests.post(
                self.audio_target_url,
                files=files
            )

            print(response.status_code)

            if response.status_code == 200:
                self.update_User_message("Аудио-файл был успешно отправлен")
                os.remove("record.wav")
                received_data = response.json()
    
                if "data" in received_data:
                    self.message_queue.put(f"{received_data['data']}")

        except Exception as e:
            print(f"An error occurred: {e}")
            os.remove("record.wav")
            

    #----------------------------Отдел Отправки аудио и сообщений----------------------------#

    # Отправить сообщение
    def send_message(self, event=None):

        message = self.entry_text.get()

        print(message)

        if not message.strip():
            return

        self.update_User_message(f"{message}")

        try:
            response = requests.post(self.text_target_url, json={"user_id" : self.user_id, "message":f"{message}"})
            
            received_data = response.json()
    
            if "data" in received_data:

                self.message_queue.put(f"{received_data['data']}")

            # elif "data" in received_data[0]["custom"] and custom_data.get("type") == "code":

            #     file_name = custom_data["file_name"]
            #     file_data = base64.b64decode(custom_data["data"])
            #     print(file_name)

            #     with open(f"{file_name}.py", "wb") as f:
            #         f.write(file_data)

            #     print(f"Новый код сохранён в файле: {file_name}.py . Вы можете им воспользоваться")

        except Exception as e:
            self.update_User_message(f"Error: {str(e)}")

        self.entry_text.delete(0, END)

    # Загрузить аудио-файл
    def upload_file_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.wav;*.mp3;*.m4a")])
        if not file_path:
            return ()

        self.update_User_message(f"Загрузка файла: {os.path.basename(file_path)}...")

        try:
            with open(file_path, "rb") as audio_file:
                files = {"audio": (os.path.basename(file_path), audio_file)}
                response = requests.post(self.audio_target_url, files=files)
                if response.status_code == 200:
                    server_response = response.json()
                    self.update_RASA_message(f"Server: {server_response.get('status', 'success')} - {server_response.get('text', '')}")
                else:
                    self.update_RASA_message(f"Server Error: {response.status_code}")
        except Exception as e:
            self.update_RASA_message(f"Error: {str(e)}")

    def init_user_id(self):

        if self.user_id == "":
            try:
                response = requests.post(self.init_user_url, timeout=5)
                response.raise_for_status()
                data = response.json()
                received_id = data.get("user_id", "")
                set_key('.env', 'USER_ID', f'{received_id}')
            except Exception as e:
                print("Не удалось инициализировать пользователя:", e)
        else:
            self.update_User_message(f"Ваш ID: {self.user_id}")

if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()