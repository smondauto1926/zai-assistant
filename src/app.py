from fastapi import FastAPI, File, UploadFile, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import torch
import whisper
import shutil
import tempfile
import json
import language_tool_python
import openai
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
import uvicorn  # For running the app locally

# Set up FastAPI app
app = FastAPI()

# Mount static folder for serving files like CSS and generated docs
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up the template rendering
templates = Jinja2Templates(directory="templates")

# Load Whisper model for transcription
device = "cpu"  # Change to "cuda" if using GPU
model = whisper.load_model("tiny", device = device)
model = model.to(torch.float32)  

# Language tool for grammar correction (though it's not used in the current code)
tool = language_tool_python.LanguageToolPublicAPI("it")

# Load OpenAI credentials
with open('openai.json', 'r') as file:
    openai_credentials = json.load(file)

API_KEY = openai_credentials['API_KEY']
openai.api_key = API_KEY

# Function to improve the transcription using GPT-4
def improve_transcript(raw_transcript):

    prompt = f"""Migliora questa trascrizione mantenendo il significato originale ma correggendo solamente:
    - Errori grammaticali
    - Punteggiatura

    Nel trascritto ci sono parole chiavi tali che devono essere solo corrette grammaticalmente e ortograficamente:
    - Caratteristiche costruttive dei fabbricati
    - Hot work
    - Ciclo produttivo
    
    Trascrizione originale:
    {raw_transcript}
    
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response["choices"][0]["message"]["content"]

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "generated_file": None})

@app.post("/transcribe/")
async def transcribe_audio(request: Request, file: UploadFile = File(...)):
    # Save the uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        shutil.copyfileobj(file.file, temp_audio)
        temp_audio_path = temp_audio.name

    try:
        # 1. Initial transcription with Whisper
        result = model.transcribe(temp_audio_path)
        raw_transcribed_text = result["text"]

        # 2. Improve transcript with GPT-4
        improved_transcript = improve_transcript(raw_transcribed_text)

        # 3. Generate analysis with GPT-4
        analysis_prompt = f"""
        Dato un testo di input, crea un report che abbia come capoverso le seguenti parole: 
        - Caratteristiche costruttive dei fabbricati
        - Hot work
        - Sistemi di spegnimento automatico
        - Rilevatori di fumo
        - Fotovoltaico
        - Ciclo produttivo

        Riporta esclusivamente il contenuto testuale senza aggiungere spiegazioni, dettagli o interpretazioni.        
        Alla fine, crea un paragrafo conclusivo di riepilogo.

        Se non trovi contenuto per le parole sopracitate, riporta: Informazione non presente 
        
        
        Questo è il testo in input da analizzare:\n\n{improved_transcript}"""
        
        analysis_response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        ai_analysis = analysis_response["choices"][0]["message"]["content"]

        # Generate Word document with all versions
        doc_path = "static/generated_summary.docx"
        document = Document()
        
        # Add title
        title = document.add_heading("Report AMFU Italia", level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # Separator
        
        # 2. Improved Transcription Section
        document.add_heading("Trascritto", level=2)
        document.add_paragraph(improved_transcript)
        
        # Separator
        document.add_paragraph("_" * 50)
        
        # 3. Analysis Section
        document.add_heading("REPORT", level=2)
        analysis_para = document.add_paragraph()
        analysis_para.add_run(":\n\n").italic = True
        document.add_paragraph(ai_analysis)

        # Save the document
        document.save(doc_path)

        # Clean up temporary file
        os.unlink(temp_audio_path)

        # Return the file path in the response as JSON
        return JSONResponse(content={"generated_file": "/static/generated_summary.docx"})

    except Exception as e:
        # Clean up temporary file in case of error
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
        raise e

# Run the app using Uvicorn when executed directly
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
