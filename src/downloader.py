import json
import os
import requests
import time
from PySide2 import QtCore, QtWebEngineWidgets, QtWidgets

HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/json",
    "X-Api-Key": "mixamo2",
    "X-Requested-With": "XMLHttpRequest",
}

session = requests.Session()

class MixamoDownloader(QtCore.QObject):
    finished = QtCore.Signal()
    total_tasks = QtCore.Signal(int)
    current_task = QtCore.Signal(int)
    task = 1
    stop = False

    def __init__(self, path, mode, query=None):
        super().__init__()
        self.path = path
        self.mode = mode
        self.query = query

    def run(self):
        character_id = self.get_primary_character_id()
        character_name = self.get_primary_character_name()
        if not character_id:
            return

        if self.mode == "tpose":
            self.total_tasks.emit(1)
            tpose_payload = self.build_tpose_payload(character_id, character_name)
            url = self.export_animation(character_id, tpose_payload)
            self.download_animation(url)
            self.finished.emit()
            return

        if self.mode == "all":
            anim_data = self.get_all_animations_data()
        elif self.mode == "query":
            anim_data = self.get_queried_animations_data(self.query)

        for anim_id, anim_name in anim_data.items():
            if self.stop:
                self.finished.emit()
                return
            anim_payload = self.build_animation_payload(character_id, anim_id)
            url = self.export_animation(character_id, anim_payload)
            self.download_animation(url)

        self.finished.emit()
        return

    def make_request(self, method, url, **kwargs):
        for _ in range(10):  # Retry 10 times
            try:
                response = session.request(method, url, timeout=30, **kwargs)
                time.sleep(3)  # Sleep for 3 seconds after each request
                return response
            except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                time.sleep(3)
                continue
        raise Exception(f"Failed to complete request to {url} after 10 retries.")

    def get_primary_character_id(self):
        response = self.make_request("GET", "https://www.mixamo.com/api/v1/characters/primary", headers=HEADERS)
        character_id = response.json().get("primary_character_id")
        return character_id

    def get_primary_character_name(self):
        response = self.make_request("GET", "https://www.mixamo.com/api/v1/characters/primary", headers=HEADERS)
        character_name = response.json().get("primary_character_name")
        return character_name

    def build_tpose_payload(self, character_id, character_name):
        self.product_name = character_name
        payload = {
            "character_id": character_id,
            "product_name": self.product_name,
            "type": "Character",
            "preferences": {"format": "fbx7_2019", "mesh": "t-pose"},
            "gms_hash": None,
        }
        tpose_payload = json.dumps(payload)
        return tpose_payload

    def get_queried_animations_data(self, query):
        page_num = 1
        params = {"limit": 96, "page": page_num, "type": "Motion", "query": query}
        response = self.make_request("GET", "https://www.mixamo.com/api/v1/products", headers=HEADERS, params=params)
        data = response.json()
        num_pages = data["pagination"]["num_pages"]
        animations = []

        while page_num <= num_pages:
            response = self.make_request("GET", "https://www.mixamo.com/api/v1/products", headers=HEADERS, params=params)
            data = response.json()
            animations.extend(data["results"])
            page_num += 1

        anim_data = {animation["id"]: animation["description"] for animation in animations}
        self.total_tasks.emit(len(anim_data))
        return anim_data

    def get_all_animations_data(self):
        anim_data = {}
        with open("mixamo_anims.json", "r") as file:
            anim_data = json.load(file)
        self.total_tasks.emit(len(anim_data))
        return anim_data

    def build_animation_payload(self, character_id, anim_id):
        response = self.make_request("GET", f"https://www.mixamo.com/api/v1/products/{anim_id}?similar=0&character_id={character_id}", headers=HEADERS)
        self.product_name = response.json().get("description")
        _type = response.json()["type"]
        preferences = {
            "format": "fbx7_2019",
            "skin": False,
            "fps": "30",
            "reducekf": "0",
        }
        gms_hash = response.json()["details"]["gms_hash"]
        gms_hash_params = gms_hash["params"]
        param_values = [int(param[-1]) for param in gms_hash_params]
        params_string = ",".join(str(val) for val in param_values)
        gms_hash["params"] = params_string
        gms_hash["overdrive"] = 0
        trim_start = int(gms_hash["trim"][0])
        trim_end = int(gms_hash["trim"][1])
        gms_hash["trim"] = [trim_start, trim_end]
        payload = {
            "character_id": character_id,
            "product_name": self.product_name,
            "type": _type,
            "preferences": preferences,
            "gms_hash": [gms_hash],
        }
        anim_payload = json.dumps(payload)
        return anim_payload

    def export_animation(self, character_id, payload):
        self.make_request("POST", "https://www.mixamo.com/api/v1/animations/export", data=payload, headers=HEADERS)
        status = None

        while status != "completed":
            time.sleep(3)
            response = self.make_request("GET", f"https://www.mixamo.com/api/v1/characters/{character_id}/monitor", headers=HEADERS)
            status = response.json().get("status")

        if status == "completed":
            download_link = response.json().get("job_result")
            return download_link

    def download_animation(self, url):
        if url:
            response = self.make_request("GET", url)
            if self.path:
                if not os.path.exists(self.path):
                    os.mkdir(self.path)
                open(f"{self.path}/{self.product_name}.fbx", "wb").write(response.content)
            else:
                open(f"{self.product_name}.fbx", "wb").write(response.content)

            self.current_task.emit(self.task)
            self.task += 1
