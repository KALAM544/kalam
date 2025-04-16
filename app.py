

from flask import Flask, request, send_from_directory, render_template
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "Aucun fichier envoyé", 400

    file = request.files['file']
    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Lecture du fichier selon extension
    if filename.endswith('.tsv'):
        df = pd.read_csv(filepath, sep='\t')
    elif filename.endswith('.json'):
        df = pd.read_json(filepath)
    elif filename.endswith('.xml'):
        df = pd.read_xml(filepath)
    elif filename.endswith('.xls') or filename.endswith('.xlsx'):
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath)

    mode = request.form.get("mode", "clean")
    normalize = mode == "full"

    df_cleaned = clean_data(df, normalize=normalize)
    cleaned_filepath = os.path.join(app.config['PROCESSED_FOLDER'], 'cleaned_' + filename)
    df_cleaned.to_csv(cleaned_filepath, index=False)

    return df_cleaned.to_html(classes="table table-striped table-bordered")

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

def normalize_data(df):
    df = df.copy()
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        scaler = StandardScaler()
        df[numeric_cols] = scaler.fit_transform(df[numeric_cols])

    object_cols = df.select_dtypes(include=['object']).columns
    for col in object_cols:
        df[col] = df[col].astype(str).str.strip().str.lower()

    df.drop_duplicates(inplace=True)
    return df
def clean_data(df, normalize=False):
    df_cleaned = df.copy()

    # Remplir les NaN numériques avec la moyenne
    df_numeric = df_cleaned.select_dtypes(include=[np.number])
    df_cleaned[df_numeric.columns] = df_numeric.fillna(df_numeric.mean())

    # Remplir les NaN catégoriques avec le mode (la valeur la plus fréquente)
    df_object = df_cleaned.select_dtypes(include=['object'])
    for col in df_object.columns:
        mode_val = df_object[col].mode().dropna()
        if not mode_val.empty:
            df_cleaned[col].fillna(mode_val[0], inplace=True)

    # Détection des outliers sur les colonnes numériques
    if not df_numeric.empty and len(df_cleaned) >= 2:
        model = IsolationForest(contamination=0.05, random_state=42)
        df_numeric = df_cleaned.select_dtypes(include=[np.number])
        df_cleaned['outlier'] = model.fit_predict(df_numeric)
        df_cleaned = df_cleaned[df_cleaned['outlier'] == 1].copy()
        df_cleaned.drop(columns=['outlier'], inplace=True, errors='ignore')

    # Normalisation si demandé
    if normalize:
        df_cleaned = normalize_data(df_cleaned)

    return df_cleaned


if __name__ == '__main__':
    app.run(debug=True)

