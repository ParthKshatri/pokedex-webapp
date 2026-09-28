from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uuid import uuid4
import cv2
import os
import tempfile

app = FastAPI()

class Pokedex:
    def __init__(self):
        self.s = []
        self.a = []
        self.load_region()

    # ---------------- REGION LOADING ----------------
    def load_region(self):

        with open("data/kanto_pokedex.txt") as k:
            self.k = k.readlines()

        with open("data/johto_region_unique.txt") as j:
            self.j = j.readlines()
        
        self.s = self.k + self.j
        self.a = [i.strip().split(",") for i in self.s]

    # ---------------- SEARCH BY NUMBER ----------------
    def search_by_number(self, number: str):
        for p in self.a:
            if p[0] == number:
                return self._pokemon_dict(p)
        return None

    # ---------------- SEARCH BY NAME ----------------
    def search_by_name(self, name: str):
        for p in self.a:
            if p[1].lower() == name.lower():
                return self._pokemon_dict(p)
        return None

    # ---------------- PARTIAL / LIVE SEARCH ----------------
    def search_partial(self, query: str, limit: int = 30):
        q = query.strip().lower()
        if not q:
            return []

        results = []
        for p in self.a:
            if len(p) < 4:
                continue
            number, name = p[0], p[1]
            if q in name.lower() or q in number:
                results.append(self._pokemon_dict(p))
                if len(results) >= limit:
                    break

        return results

    # ---------------- CAMERA IMAGE MATCH ----------------
    def camera_search_from_image(self, image_path: str):
        print("Running ORB detection...")

        path = "static/pokemon_images"
        images = os.listdir(path)

        orb = cv2.ORB_create(nfeatures=1000)
        ref_data = []

        # Load reference images
        for img in images:
            full = os.path.join(path, img)
            ref_img = cv2.imread(full, 0)

            if ref_img is None:
                continue

            kp, des = orb.detectAndCompute(ref_img, None)
            if des is not None:
                ref_data.append((img, des))

        captured = cv2.imread(image_path, 0)
        if captured is None:
            return None

        # HARD REJECT: document / text images
        edges = cv2.Canny(captured, 50, 150)
        edge_density = edges.mean() / 255
        if edge_density > 0.15:
            print("Rejected: document-like image")
            return None

        kp2, des2 = orb.detectAndCompute(captured, None)
        if des2 is None or len(kp2) < 100:
            print("Rejected: insufficient features")
            return None

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        scores = []

        for img, des1 in ref_data:
            matches = bf.match(des1, des2)
            good = [m for m in matches if m.distance < 40]

            if len(good) < 30:
                continue

            match_ratio = len(good) / max(len(des1), 1)
            scores.append((img, len(good), match_ratio))

        if not scores:
            print("Rejected: no strong matches")
            return None

        scores.sort(key=lambda x: (x[1], x[2]), reverse=True)

        best_img, best_score, best_ratio = scores[0]

        if best_ratio < 0.02:
            print("Rejected: match ratio too low")
            return None

        pokemon_name = best_img.split("_")[1].split(".")[0].strip()
        print("Detected Pokémon:", pokemon_name)
        return pokemon_name


    # ---------------- HELPER ----------------
    def _pokemon_dict(self, p):
        return {
            "number": p[0],
            "name": p[1],
            "type": p[2],
            "description": p[3]
        }
    
    # ---------------- FASTAPI ----------------
pokedex = Pokedex()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    image_list = os.listdir("static/pokemon_images")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "images": image_list,
            "pokemon": None
        }
        )    
@app.get("/search")
def search(query: str):
    pokedex.load_region()  # ensure data is loaded

    if query.isdigit():
        return pokedex.search_by_number(query)
    else:
        return pokedex.search_by_name(query)


@app.get("/search/live")
def search_live(query: str):
    pokedex.load_region()  # ensure data is loaded
    return pokedex.search_partial(query)

@app.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    print("DETECT IMAGE ENDPOINT HIT") 
    filename = os.path.join(tempfile.gettempdir(), f"{uuid4().hex}.png")
    try:
        with open(filename, "wb") as f:
            f.write(await file.read())

        pokemon_name = pokedex.camera_search_from_image(filename)
    finally:
        if os.path.exists(filename):
            os.remove(filename)

    if not pokemon_name:
        return {"found": False}

    return {"found": True, "name": pokemon_name}

# ----------------- AUTHENTICATION -----------------

from pydantic import BaseModel
import database

# Initialize DB
database.init_db()

class UserAuth(BaseModel):
    username: str
    password: str

class PokemonAction(BaseModel):
    pokemon_name: str
    location: str # 'team' or 'storage'

@app.post("/api/register")
def register(user_data: UserAuth):
    success, message = database.register_user(user_data.username, user_data.password)
    if not success:
        return {"success": False, "message": message}
    return {"success": True, "message": "Registered successfully"}

@app.post("/api/login")
def login(user_data: UserAuth, response: Request): # Request just for type hint, actual response needed
    token, error = database.login_user(user_data.username, user_data.password)
    if not token:
        return {"success": False, "message": error}
    
    # We need to return a response with cookie
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content={"success": True, "token": token})
    resp.set_cookie(key="session_token", value=token)
    return resp

@app.post("/api/logout")
def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        database.logout_user(token)
    
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content={"success": True})
    resp.delete_cookie("session_token")
    return resp

@app.get("/api/me")
def get_me(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        return {"logged_in": False}
    
    user = database.get_user_by_token(token)
    if not user:
        return {"logged_in": False}
        
    user_id = user[0] # (id, username)
    
    # Get user specific list
    team, storage = database.get_user_pokemon(user_id)
    
    return {
        "logged_in": True,
        "username": user[1],
        "team": team,
        "storage": storage
    }

@app.post("/api/pokemon/add")
def add_user_pokemon(action: PokemonAction, request: Request):
    token = request.cookies.get("session_token")
    user = database.get_user_by_token(token) if token else None
    
    if not user:
        return {"success": False, "message": "Not logged in"}
    
    database.add_pokemon(user[0], action.pokemon_name, action.location)
    return {"success": True}

@app.post("/api/pokemon/remove")
def remove_user_pokemon(action: PokemonAction, request: Request):
    token = request.cookies.get("session_token")
    user = database.get_user_by_token(token) if token else None
    
    if not user:
        return {"success": False, "message": "Not logged in"}
    
    database.remove_pokemon(user[0], action.pokemon_name, action.location)
    return {"success": True}
