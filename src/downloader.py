# Stdlib modules
import json
import os
import requests
import time

# Third-party modules
from PySide2 import QtCore, QtWebEngineWidgets, QtWidgets


HEADERS = {
"Accept": "application/json",
"Accept-Encoding":"gzip, deflate, br, zstd",
"Content-Type": "application/json",
"X-Api-Key": "mixamo2",
"X-Requested-With": "XMLHttpRequest",
}

# All requests will be done through a session to improve performance.
session = requests.Session()


class MixamoDownloader(QtCore.QObject):
  """Bulk download animations from Mixamo.

  Users can choose to download all animations in Mixamo (quite slow),
  only those that contain a specific word (faster), or just the T-Pose.

  The download mode is to be passed onto this class as an argument
  when creating an instance.

  The first step is to get the primary character ID and name.


  """
  # Create signals that will be used to emit info to the UI.
  finished = QtCore.Signal()
  total_tasks = QtCore.Signal(int)
  current_task = QtCore.Signal(int)

  # Initialize a counter for the progress bar.
  task = 1
  
  # Initialize a flag that tells the code to stop.
  stop = False

  def __init__(self, path, mode, query=None):
    """Initialize the Mixamo Downloader object.

    :param path: Output folder path
    :type path: str

    :param mode: Download mode ("all", "query" or "tpose")
    :type mode: str

    :param query: Keyword to be used as query when searching animations
    :type query: str
    """
    super().__init__()

    self.path = path
    self.mode = mode
    self.query = query

  def run(self):
    # Get the primary character ID and name.
    character_id = self.get_primary_character_id()
    character_name = self.get_primary_character_name()
    
    # If there's no character ID, it means that there was some problem
    # with the access token, so we better stop the code at this point. 
    if not character_id:
      return

    # DOWNLOAD MODE: TPOSE
    if self.mode == "tpose":
      # The total amount of tasks to process is 1.
      self.total_tasks.emit(1)

      # Build the T-Pose payload.
      tpose_payload = self.build_tpose_payload(character_id, character_name)

      # Export and download the T-Pose.
      url = self.export_animation(character_id, tpose_payload)

      #print(f"Downloading T-Pose (with skin) for {character_name}...")
      self.download_animation(url)
      #print(f"T-Pose successfully downloaded.")

      # Emit the 'finished' signal to let the UI know that worker is done.
      self.finished.emit()
      return

    # DOWNLOAD MODE: ALL
    if self.mode == "all":
      # Get animation IDs from the JSON file on disk.
      anim_data = self.get_all_animations_data()

    # DOWNLOAD MODE: QUERY
    elif self.mode == "query":
      # Search for animation IDs according to the query entered by the user.
      anim_data = self.get_queried_animations_data(self.query)

    # The following code will be run for both the "all" and "query" modes.
    # Iterate the animation IDs and names dictionary.
    for anim_id, anim_name in anim_data.items():

      # Check if the 'Stop' button has been pressed in the UI.
      if self.stop:

        # Let the thread know that the worker has finished the job.
        # Stopping the function here with a return makes the thread actually
        # finish. Without it, the thread would remain active until every line
        # of this method is done.
        self.finished.emit()
        return

      # Build the animation payload, export and download it to disk.
      anim_payload = self.build_animation_payload(character_id, anim_id)
      url = self.export_animation(character_id, anim_payload)

      #print(f"Downloading {anim_name}...")
      self.download_animation(url)

    #print("DOWNLOAD COMPLETE.")
    # Emit the 'finished' signal to let the UI know that worker is done.
    self.finished.emit()
    return

  def get_primary_character_id(self):
    """Get the primary character ID (i.e: the one selected by the user).

    :return: Primary character ID
    :rtype: str
    """
    # Send a GET request to the primary character endpoint.
    response = session.get(
      f"https://www.mixamo.com/api/v1/characters/primary",
      headers=HEADERS)

    # Get the primary character ID.
    character_id = response.json().get("primary_character_id")

    return character_id

  def get_primary_character_name(self):
    """Get the primary character name (i.e: the one selected by the user).

    :return: Primary character name
    :rtype: str
    """
    # Send a GET request to the primary character endpoint.
    response = session.get(
      f"https://www.mixamo.com/api/v1/characters/primary",
      headers=HEADERS)

    # Get the primary character name.
    character_name = response.json().get("primary_character_name")

    return character_name

  def build_tpose_payload(self, character_id, character_name):
    """Build the payload that will be used to export the T-Pose.

    :param character_id: Primary character ID
    :type character_id: str

    :param character_name: Primary character name
    :type character name: str

    :return: Payload that will be used to export the T-Pose
    :rtype: str
    """
    # Update the 'product_name' variable so that it can be used later
    # as the FBX file name (see the 'download_animation' method).
    self.product_name = character_name

    # Build the payload.
    payload = {
      "character_id": character_id,
      "product_name": self.product_name,
      "type": "Character",
      "preferences": {"format":"fbx7_2019", "mesh":"t-pose"},
      "gms_hash": None
    }

    # Convert the payload dictionary into a JSON string.
    tpose_payload = json.dumps(payload)    

    return tpose_payload

  def get_queried_animations_data(self, query):
    """Get the ID and name of every animation found by the user query.

    :return: Queried animation IDs and names
    :rtype: dict
    """
    # Initialize a counter for the page number.
    page_num = 1

    # Parameters to be passed onto the endpoint.
    params = {
      "limit":96,
      "page":page_num,
      "type":"Motion",
      "query": query}

    # Send a GET request to the animations endpoint.
    response = session.get("https://www.mixamo.com/api/v1/products",
      headers=HEADERS,
      params=params)

    data = response.json()

    # Total number of pages.
    num_pages = data["pagination"]["num_pages"]

    # Initialize a list to store all animations found.
    animations = []

    # Make sure we read every page and grab the animations therein.
    while page_num <= num_pages:

      response = session.get("https://www.mixamo.com/api/v1/products",
        headers=HEADERS,
        params=params)

      data = response.json()

      # Add animations to the list and increase the page counter by one.
      animations.extend(data["results"])
      page_num += 1

    # Initialize a dictionary to store IDs and names.
    anim_data = {}

    # Iterate animations found by the query and add them to the dictionary. 
    for animation in animations:      
      anim_data[animation["id"]] = animation["description"]

    # Let the UI know how many animations are to be downloaded.
    self.total_tasks.emit(len(anim_data))    

    return anim_data

  def get_all_animations_data(self):
    """Get the ID and name of every animation in Mixamo.

    To speed things up, all animations have been previously exported to a
    JSON file that we'll be reading locally. This is way faster than getting
    all animations on the fly every time you run the tool.

    Mixamo doesn't seem to add new animations very often, so we're OK with
    using a pre-saved local file.

    The JSON file might be updated on GitHub if we know of any new entries.

    :return: All animation IDs and names
    :rtype: dict   
    """
    # Initialize a dictionary to store all animation IDs and names.
    anim_data = {}

    # Read the local JSON file and dump its content to the dictionary.
    with open("mixamo_anims.json", "r") as file:
      anim_data = json.load(file)

    # Let the UI know how many animations are to be downloaded.    
    self.total_tasks.emit(len(anim_data))
    
    return anim_data

  def build_animation_payload(self, character_id, anim_id):
    """Build the payload that will be used to export the animation.

    :param character_id: Primary character ID
    :type character_id: str

    :param anim_id: Animation ID
    :type anim_id: str

    :return: Payload that will be used to export the animation
    :rtype: str
    """
    # Send a GET request to the animation-on-character endpoint.
    response = session.get(
      f"https://www.mixamo.com/api/v1/products/{anim_id}?similar=0&character_id={character_id}",
      headers=HEADERS)

    # Get the animation description (make it public so that we can use it later).
    # We're using the description because some anims have the same name and this
    # would cause them to be overriden when downloading to disk.
    self.product_name = response.json()["description"]
    # Get the animation type.
    _type = response.json()["type"]

    # Set the animation preferences.
    # NOTE: Changing the 'skin' key to True doesn't seem to have any effect.
    preferences =   {
      "format": "fbx7_2019",
      "skin": False,
      "fps": "24",
      "reducekf": "0"
    }

    # Get the original 'gms_hash' property.
    gms_hash = response.json()["details"]["gms_hash"]

    # Read its 'params' and store their values.
    gms_hash_params = gms_hash["params"]
    param_values = [int(param[-1]) for param in gms_hash_params]       

    # Build a 'params' string depending on how many params the animation has.
    # For example, if there are two params (Overdrive and Emotion), and their
    # values are 1 and 0, the string will be "1,0".
    params_string = "," .join(str(val) for val in param_values)

    # Update the 'gms_hash' properties with the ones Mixamo actually needs.
    gms_hash["params"] = params_string
    gms_hash["overdrive"] = 0

    trim_start = int(gms_hash["trim"][0])
    trim_end = int(gms_hash["trim"][1])

    gms_hash["trim"] = [trim_start, trim_end]

    # Build the payload.
    payload = {
        "character_id": character_id,
        "product_name": self.product_name,
        "type": _type,
        "preferences": preferences,
        "gms_hash": [gms_hash]
    }

    # Convert the payload dictionary into a JSON string.
    anim_payload = json.dumps(payload)

    return anim_payload

  def export_animation(self, character_id, payload):
    """Export the animation and retrieve the download link.

    :param character_id: Primary character ID
    :type character_id: str

    :param payload: Payload that will be used to export the animation
    :type payload: str

    :return: URL to download the animation
    :rtype: str
    """
    # Send a POST request to the export animations endpoint.
    response = session.post(f"https://www.mixamo.com/api/v1/animations/export",
      data=payload,
      headers=HEADERS)

    # Initialize a 'status' flag.
    status = None

    # Check if the process is completed and retry if it's not.
    while status != "completed":
      # Add some delay between retries to avoid overflow. 
      time.sleep(1)

      # Send a GET request to the monitor endpoint.
      response = session.get(f"https://www.mixamo.com/api/v1/characters/{character_id}/monitor",
        headers=HEADERS)

      # The loop will end as soon as the status is 'completed'.
      status = response.json().get("status")
    
    # Grab the download link from the response.
    if status == "completed":
      download_link = response.json().get("job_result")

      return download_link

  def download_animation(self, url):
    """Download the animation to disk.

    :param url: URL to download the animation
    :type url: str
    """
    # Ensure this code is only run if a URL has been retrieved.
    if url:
      # Send a GET request to the download link.
      response = session.get(url)

      # Check if the output folder exists on disk. If it doesn't, create it.
      if self.path:
        if not os.path.exists(self.path):
          os.mkdir(self.path)

        # Save the response into a new FBX file called after the animation name.
        open(f"{self.path}/{self.product_name}.fbx", "wb").write(response.content)

      # If no output path has been set by the user, save the FBX to the cwd
      # (i.e: the folder where this Python script is being executed).
      else:
        open(f"{self.product_name}.fbx", "wb").write(response.content)

      # Let the UI know that a task has been completed.
      self.current_task.emit(self.task)
      # Increase the counter by one.
      self.task += 1
