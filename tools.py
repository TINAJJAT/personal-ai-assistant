import os
import requests

from dotenv import load_dotenv # load the env
from langchain.tools import tool # to define tools
from langchain_tavily import TavilySearch # for web search tool
from langchain_google_community import GmailToolkit # for gmail
from langchain_google_community import CalendarToolkit # for google calendar
from googleapiclient.discovery import build # for youtube

from langchain_google_community.calendar.utils import (
    get_google_credentials, # handles Google OAuth authentication
    build_calendar_service, # use those authenticated credentials to construct an acutal Google Calendar API client
)

# load the env
load_dotenv()

# Weather API key (Openweather)
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

# =================================================
# Calculator tool
# =================================================
@tool
def calculator_tool(a: float, b:float, operation:str) -> float:
    """
    Perform addition, subtraction, multiplication, or division on two numbers.
    """

    if operation == "add":
        return a + b

    elif operation == "subtract":
        return a - b

    elif operation == "multiply":
        return a * b

    elif operation == "divide":
        if b == 0:
            return "Cannot divide by zero"
        return a / b
    
    else:
        return "Invalid operation"

# =================================================
# Websearch tool (Tavily Search)
# =================================================
tavily_search = TavilySearch(api_key=TAVILY_API_KEY, max_results=5)

# =================================================
# Weather tool
# =================================================
@tool
def get_weather(city:str) -> str:
    """
    Get the current weather for a given city.
    """
    url = f"http://api.openweathermap.org/data/2.5/weather"

    params = {
        "q": city,
        "appid": WEATHER_API_KEY,
        "units": "metric"
    }

    try:

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if response.status_code != 200:
            return f"Weather error: {data.get('message', 'Unknown error')}"

        return (
            f"Weather in {city}: " 
            f"{data['main']['temp']}°C, " 
            f"{data['weather'][0]['description']}, "
            f"Humidity: {data['main']['humidity']}%" 
        )

    except Exception as e:
        return f"Weather request failed: {e}"


# ================================================
# Gmail
# ================================================
gmail_toolkit = GmailToolkit()
gmail_tools = gmail_toolkit.get_tools()

# ===============================================
# Google Calendar
# ===============================================
calendar_credentials = get_google_credentials(
    token_file="calendar_token.json",
    scopes=[
        "https://www.googleapis.com/auth/calendar"
    ],
    client_secrets_file="credentials.json",
)

calendar_service = build_calendar_service(
    credentials=calendar_credentials
)

calendar_toolkit = CalendarToolkit(
    api_resource=calendar_service
)

calendar_tools = calendar_toolkit.get_tools()

# ================================================
# Youtube search
# ===============================================
import webbrowser
@tool
def youtube_search(query: str, max_results: int = 5) -> str:
    """
    Search YouTube for videos related to a user's query.

    Use this tool when the user wants to find, search for,
    or discover YouTube videos.
    """

    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

    if not YOUTUBE_API_KEY:
        return "YouTube API key is not configured."

    try:
        youtube = build(
            "youtube",
            "v3",
            developerKey=YOUTUBE_API_KEY
        )

        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results
        )

        response = request.execute()

        if not response["items"]:
            return "No YouTube videos found."

        video_id = response["items"][0]["id"]["videoId"]
        title = response["items"][0]["snippet"]["title"]

        url = f"https://www.youtube.com/watch?v={video_id}"

        webbrowser.open(url)

        return f"Playing '{title}' on YouTube"

    except Exception as e:
        return f"YouTube search failed: {str(e)}"

# =================================================
# Google Drive
# =================================================

import os
from pathlib import Path

from langchain.tools import tool

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# -------------------------------------------------
# Google Drive OAuth settings
# -------------------------------------------------

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

DRIVE_CREDENTIALS_FILE = "credentials.json"
DRIVE_TOKEN_FILE = "drive_token.json"


# -------------------------------------------------
# Get Google Drive credentials
# -------------------------------------------------

def get_drive_credentials():

    creds = None

    # -------------------------------------------------
    # Load existing token
    # -------------------------------------------------
    if os.path.exists(DRIVE_TOKEN_FILE):

        creds = Credentials.from_authorized_user_file(
            DRIVE_TOKEN_FILE,
            DRIVE_SCOPES
        )

    # -------------------------------------------------
    # If token is missing or invalid
    # -------------------------------------------------
    if not creds or not creds.valid:

        # Refresh expired token
        if creds and creds.expired and creds.refresh_token:

            creds.refresh(Request())

        # Otherwise perform OAuth login
        else:

            flow = InstalledAppFlow.from_client_secrets_file(
                DRIVE_CREDENTIALS_FILE,
                DRIVE_SCOPES
            )

            creds = flow.run_local_server(
                port=0
            )

        # Save token
        with open(DRIVE_TOKEN_FILE, "w") as token:

            token.write(
                creds.to_json()
            )

    return creds


# -------------------------------------------------
# Build Google Drive service
# -------------------------------------------------

drive_credentials = get_drive_credentials()

drive_service = build(
    "drive",
    "v3",
    credentials=drive_credentials
)


# -------------------------------------------------
# Tool 1 - Search files
# -------------------------------------------------

@tool
def search_drive_files(query: str) -> str:
    """
    Search Google Drive for files or folders by name.

    Use this tool when the user asks to find or search
    for something in Google Drive.
    """

    try:

        safe_query = query.replace("'", "\\'")

        response = drive_service.files().list(
            q=f"name contains '{safe_query}' and trashed = false",
            fields="files(id, name, mimeType, webViewLink)",
            pageSize=10
        ).execute()

        files = response.get(
            "files",
            []
        )

        if not files:

            return f"No Google Drive files found matching '{query}'."

        results = []

        for file in files:

            results.append(
                f"""
Name: {file.get("name")}
ID: {file.get("id")}
Type: {file.get("mimeType")}
Link: {file.get("webViewLink", "No link available")}
"""
            )

        return "\n".join(results)

    except Exception as e:

        return f"Google Drive search failed: {e}"


# -------------------------------------------------
# Tool 2 - List recent files
# -------------------------------------------------

@tool
def list_drive_files(limit: int = 10) -> str:
    """
    List recent files from Google Drive.

    Use this tool when the user asks to see their
    recent Drive files.
    """

    try:

        response = drive_service.files().list(
            pageSize=limit,
            orderBy="modifiedTime desc",
            q="trashed = false",
            fields=(
                "files("
                "id,"
                "name,"
                "mimeType,"
                "modifiedTime,"
                "webViewLink"
                ")"
            )
        ).execute()

        files = response.get(
            "files",
            []
        )

        if not files:

            return "No files found in Google Drive."

        results = []

        for file in files:

            results.append(
                f"""
Name: {file.get("name")}
ID: {file.get("id")}
Type: {file.get("mimeType")}
Modified: {file.get("modifiedTime")}
Link: {file.get("webViewLink", "No link available")}
"""
            )

        return "\n".join(results)

    except Exception as e:

        return f"Failed to list Drive files: {e}"


# -------------------------------------------------
# Tool 3 - Create folder
# -------------------------------------------------

@tool
def create_drive_folder(folder_name: str) -> str:
    """
    Create a folder in Google Drive.

    Use this tool when the user asks to create
    a new Google Drive folder.
    """

    try:

        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }

        folder = drive_service.files().create(
            body=metadata,
            fields="id, name, webViewLink"
        ).execute()

        return (
            f"Folder created successfully.\n"
            f"Name: {folder.get('name')}\n"
            f"ID: {folder.get('id')}\n"
            f"Link: {folder.get('webViewLink', 'Not available')}"
        )

    except Exception as e:

        return f"Failed to create Drive folder: {e}"


# -------------------------------------------------
# Tool 4 - Rename file/folder
# -------------------------------------------------

@tool
def rename_drive_file(
    file_id: str,
    new_name: str
) -> str:
    """
    Rename a Google Drive file or folder.

    Requires the Drive file ID.
    """

    try:

        updated_file = drive_service.files().update(
            fileId=file_id,
            body={
                "name": new_name
            },
            fields="id, name, webViewLink"
        ).execute()

        return (
            f"Renamed successfully.\n"
            f"New name: {updated_file.get('name')}\n"
            f"ID: {updated_file.get('id')}"
        )

    except Exception as e:

        return f"Failed to rename Drive file: {e}"


# -------------------------------------------------
# Tool 5 - Move file to trash
# -------------------------------------------------

@tool
def trash_drive_file(file_id: str) -> str:
    """
    Move a Google Drive file or folder to trash.

    Use this instead of permanently deleting files.
    """

    try:

        file = drive_service.files().update(
            fileId=file_id,
            body={
                "trashed": True
            },
            fields="id, name, trashed"
        ).execute()

        return (
            f"Moved to trash successfully.\n"
            f"Name: {file.get('name')}\n"
            f"ID: {file.get('id')}"
        )

    except Exception as e:

        return f"Failed to move Drive file to trash: {e}"


# -------------------------------------------------
# Tool 6 - Restore file from trash
# -------------------------------------------------

@tool
def restore_drive_file(file_id: str) -> str:
    """
    Restore a Google Drive file or folder from trash.
    """

    try:

        file = drive_service.files().update(
            fileId=file_id,
            body={
                "trashed": False
            },
            fields="id, name, trashed"
        ).execute()

        return (
            f"Restored successfully.\n"
            f"Name: {file.get('name')}\n"
            f"ID: {file.get('id')}"
        )

    except Exception as e:

        return f"Failed to restore Drive file: {e}"


# -------------------------------------------------
# Tool 7 - Upload local file
# -------------------------------------------------

@tool
def upload_file_to_drive(
    file_path: str
) -> str:
    """
    Upload a local file to Google Drive.

    The file_path must point to an existing local file.
    """

    try:

        path = Path(file_path)

        if not path.exists():

            return f"File does not exist: {file_path}"

        media = MediaFileUpload(
            str(path),
            resumable=True
        )

        metadata = {
            "name": path.name
        }

        uploaded_file = drive_service.files().create(
            body=metadata,
            media_body=media,
            fields="id, name, webViewLink"
        ).execute()

        return (
            f"File uploaded successfully.\n"
            f"Name: {uploaded_file.get('name')}\n"
            f"ID: {uploaded_file.get('id')}\n"
            f"Link: {uploaded_file.get('webViewLink', 'Not available')}"
        )

    except Exception as e:

        return f"Drive upload failed: {e}"


# -------------------------------------------------
# Tool 8 - Permanently delete file
# -------------------------------------------------

@tool
def delete_drive_file(
    file_id: str
) -> str:
    """
    Permanently delete a Google Drive file.

    This operation cannot normally be undone.
    Use only when the user explicitly requests
    permanent deletion.
    """

    try:

        drive_service.files().delete(
            fileId=file_id
        ).execute()

        return (
            f"Google Drive file with ID "
            f"{file_id} was permanently deleted."
        )

    except Exception as e:

        return f"Failed to delete Drive file: {e}"


# -------------------------------------------------
# Google Drive tools
# -------------------------------------------------

drive_tools = [
    search_drive_files,
    list_drive_files,
    create_drive_folder,
    rename_drive_file,
    trash_drive_file,
    restore_drive_file,
    upload_file_to_drive,
    delete_drive_file,
]

# =================================================
# Google Sheets
# =================================================

import os

from langchain.tools import tool

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from googleapiclient.discovery import build


# =================================================
# Google Sheets OAuth settings
# =================================================

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

SHEETS_CREDENTIALS_FILE = "credentials.json"
SHEETS_TOKEN_FILE = "sheets_token.json"


# =================================================
# Get Google Sheets credentials
# =================================================

def get_sheets_credentials():

    creds = None

    # ---------------------------------------------
    # Load existing token
    # ---------------------------------------------
    if os.path.exists(SHEETS_TOKEN_FILE):

        creds = Credentials.from_authorized_user_file(
            SHEETS_TOKEN_FILE,
            SHEETS_SCOPES
        )

    # ---------------------------------------------
    # Token missing or invalid
    # ---------------------------------------------
    if not creds or not creds.valid:

        # Refresh expired token
        if creds and creds.expired and creds.refresh_token:

            creds.refresh(Request())

        # Otherwise perform OAuth login
        else:

            flow = InstalledAppFlow.from_client_secrets_file(
                SHEETS_CREDENTIALS_FILE,
                SHEETS_SCOPES
            )

            creds = flow.run_local_server(
                port=0
            )

        # Save token
        with open(SHEETS_TOKEN_FILE, "w") as token:

            token.write(
                creds.to_json()
            )

    return creds


# =================================================
# Build Google Sheets service
# =================================================

sheets_credentials = get_sheets_credentials()

sheets_service = build(
    "sheets",
    "v4",
    credentials=sheets_credentials
)


# =================================================
# Tool 1 - Create spreadsheet
# =================================================

@tool
def create_spreadsheet(title: str) -> str:
    """
    Create a new Google Spreadsheet.

    Use this tool when the user asks to create
    a new spreadsheet.
    """

    try:

        spreadsheet = {
            "properties": {
                "title": title
            }
        }

        result = sheets_service.spreadsheets().create(
            body=spreadsheet,
            fields="spreadsheetId,properties(title),spreadsheetUrl"
        ).execute()

        return (
            f"Spreadsheet created successfully.\n"
            f"Title: {result['properties']['title']}\n"
            f"Spreadsheet ID: {result['spreadsheetId']}\n"
            f"URL: {result.get('spreadsheetUrl')}"
        )

    except Exception as e:

        return f"Failed to create spreadsheet: {e}"


# =================================================
# Tool 2 - Read sheet data
# =================================================

@tool
def read_sheet(
    spreadsheet_id: str,
    range_name: str
) -> str:
    """
    Read values from a Google Sheet.

    spreadsheet_id:
    The spreadsheet ID from the Google Sheets URL.

    range_name examples:
    Sheet1!A1:D10
    Sheet1!A:A
    Sheet1
    """

    try:

        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()

        values = result.get(
            "values",
            []
        )

        if not values:

            return "No data found in the requested range."

        rows = []

        for row in values:
            rows.append(" | ".join(map(str, row)))

        return "\n".join(rows)

    except Exception as e:

        return f"Failed to read spreadsheet: {e}"


# =================================================
# Tool 3 - Update sheet range
# =================================================

@tool
def update_sheet(
    spreadsheet_id: str,
    range_name: str,
    values: list[list]
) -> str:
    """
    Update cells in a Google Sheet.

    Example:
    range_name = "Sheet1!A1:B2"

    values = [
        ["Name", "Score"],
        ["Tina", 95]
    ]
    """

    try:

        body = {
            "values": values
        }

        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()

        return (
            f"Spreadsheet updated successfully.\n"
            f"Updated range: {result.get('updatedRange')}\n"
            f"Updated cells: {result.get('updatedCells')}"
        )

    except Exception as e:

        return f"Failed to update spreadsheet: {e}"


# =================================================
# Tool 4 - Append rows
# =================================================

@tool
def append_sheet_rows(
    spreadsheet_id: str,
    range_name: str,
    values: list[list]
) -> str:
    """
    Append new rows to a Google Sheet.

    Example:
    range_name = "Sheet1!A:C"

    values = [
        ["2026-09-11", "Interview", "Completed"]
    ]
    """

    try:

        body = {
            "values": values
        }

        result = sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        updates = result.get(
            "updates",
            {}
        )

        return (
            f"Rows appended successfully.\n"
            f"Updated range: {updates.get('updatedRange')}\n"
            f"Updated rows: {updates.get('updatedRows')}"
        )

    except Exception as e:

        return f"Failed to append rows: {e}"


# =================================================
# Tool 5 - Clear cells
# =================================================

@tool
def clear_sheet_range(
    spreadsheet_id: str,
    range_name: str
) -> str:
    """
    Clear values from a range in Google Sheets.

    Example:
    Sheet1!A2:D20
    """

    try:

        sheets_service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            body={}
        ).execute()

        return (
            f"Successfully cleared range: {range_name}"
        )

    except Exception as e:

        return f"Failed to clear range: {e}"


# =================================================
# Tool 6 - Add new sheet/tab
# =================================================

@tool
def add_sheet_tab(
    spreadsheet_id: str,
    sheet_name: str
) -> str:
    """
    Add a new worksheet/tab to an existing spreadsheet.
    """

    try:

        request_body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": sheet_name
                        }
                    }
                }
            ]
        }

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return (
            f"Sheet tab '{sheet_name}' created successfully."
        )

    except Exception as e:

        return f"Failed to create sheet tab: {e}"


# =================================================
# Tool 7 - Rename sheet/tab
# =================================================

@tool
def rename_sheet_tab(
    spreadsheet_id: str,
    sheet_id: int,
    new_name: str
) -> str:
    """
    Rename a worksheet/tab.

    sheet_id is the numeric ID of the tab,
    not the spreadsheet ID.
    """

    try:

        body = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "title": new_name
                        },
                        "fields": "title"
                    }
                }
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        return (
            f"Sheet tab renamed successfully to '{new_name}'."
        )

    except Exception as e:

        return f"Failed to rename sheet tab: {e}"


# =================================================
# Google Sheets tools
# =================================================

sheets_tools = [
    create_spreadsheet,
    read_sheet,
    update_sheet,
    append_sheet_rows,
    clear_sheet_range,
    add_sheet_tab,
    rename_sheet_tab,
]

# =================================================
# Local File Management
# =================================================
from langchain_community.agent_toolkits import FileManagementToolkit

file_toolkit = FileManagementToolkit(
    root_dir="./assistant_files"
)

file_tools = file_toolkit.get_tools()

# =================================================
# Notepad - Open and Write
# =================================================

from langchain.tools import tool
from pywinauto import Application


@tool
def write_in_notepad(text: str) -> str:
    """
    Open Windows Notepad and write the given text into it.

    Use this tool when the user asks to open Notepad
    and type or write content.
    """

    try:
        app = Application(backend="uia").start("notepad.exe")

        window = app.window(title_re=".*Notepad")

        window.wait(
            "visible",
            timeout=10
        )

        editor = window.child_window(
            control_type="Edit"
        )

        editor.set_edit_text(text)

        return "Text written successfully in Notepad."

    except Exception as e:
        return f"Failed to write in Notepad: {e}"

@tool
def append_to_notepad(text: str) -> str:
    """
    Append text to an already-open Notepad window.
    """

    try:
        app = Application(backend="uia").connect(
            title_re=".*Notepad"
        )

        window = app.window(title_re=".*Notepad")

        editor = window.child_window(
            control_type="Edit"
        )

        existing_text = editor.window_text()

        new_text = existing_text + "\n" + text

        editor.set_edit_text(new_text)

        return "Text appended successfully."

    except Exception as e:
        return f"Failed to append text in Notepad: {e}"

# =================================================
# Tools list
# =================================================
tools = [
    calculator_tool,
    tavily_search,
    get_weather,
    *gmail_tools,
    *calendar_tools,
    youtube_search,
    *drive_tools,
    *sheets_tools,
    *file_tools,
    write_in_notepad,
    append_to_notepad
]