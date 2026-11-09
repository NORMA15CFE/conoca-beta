import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
from werkzeug.utils import secure_filename
from datetime import datetime
import openpyxl

app = Flask(__name__)
app.secret_key = 'clave_secreta_conoca_cfe_2026'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expedientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zona TEXT,
            rpe TEXT,
            empleado TEXT,
            cat_actual TEXT,
            cat_impacta TEXT,
            evaluacion TEXT,
            alto_riesgo TEXT,
            bateria_constancia TEXT,
            estatus TEXT,
            curso_acreditado TEXT,
            cumple_bateria TEXT
        )
    ''')
    
    # Migraciones automáticas seguras para columnas nuevas
    cursor.execute("PRAGMA table_info(expedientes)")
    columnas = [col[1] for col in cursor.fetchall()]
    if 'curso_acreditado' not in columnas:
        cursor.execute("ALTER TABLE expedientes ADD COLUMN curso_acreditado TEXT")
    if 'cumple_bateria' not in columnas:
        cursor.execute("ALTER TABLE expedientes ADD COLUMN cumple_bateria TEXT")
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    usuario = request.form.get('usuario') or request.form.get('zona')
    password = request.form.get('password')
    if usuario and password:
        session['usuario'] = usuario
        return redirect(url_for('dashboard'))
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('index'))
    
    zona_filtro = request.args.get('zona', '')
    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    
    if zona_filtro and zona_filtro != "-- Todas las Zonas --":
        cursor.execute("SELECT * FROM expedientes WHERE zona = ?", (zona_filtro,))
    else:
        cursor.execute("SELECT * FROM expedientes")
        
    expedientes = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT zona FROM expedientes WHERE zona IS NOT NULL AND zona != ''")
    zonas = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return render_template('dashboard.html', expedientes=expedientes, zonas=zonas, zona_actual=zona_filtro)

@app.route('/agregar', methods=['POST'])
def agregar():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    zona = request.form.get('zona')
    rpe = request.form.get('rpe')
    empleado = request.form.get('empleado')
    cat_actual = request.form.get('cat_actual')
    cat_impacta = request.form.get('cat_impacta')
    evaluacion = request.form.get('evaluacion')
    alto_riesgo = request.form.get('alto_riesgo')
    estatus = request.form.get('estatus', 'Pendiente')
    curso_acreditado = request.form.get('curso_acreditado')
    cumple_bateria = request.form.get('cumple_bateria')
    
    bateria_filename = ""
    if cumple_bateria == "Sí" and 'bateria_constancia' in request.files:
        file = request.files['bateria_constancia']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            bateria_filename = filename

    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO expedientes (zona, rpe, empleado, cat_actual, cat_impacta, evaluacion, alto_riesgo, bateria_constancia, estatus, curso_acreditado, cumple_bateria)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (zona, rpe, empleado, cat_actual, cat_impacta, evaluacion, alto_riesgo, bateria_filename, estatus, curso_acreditado, cumple_bateria))
    conn.commit()
    conn.close()
    
    return redirect(url_for('dashboard'))

@app.route('/descargar_reporte_mensual', methods=['GET'])
def descargar_reporte_mensual():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    cursor.execute("SELECT zona, rpe, empleado, cat_actual, cat_impacta, evaluacion, alto_riesgo, estatus, curso_acreditado, cumple_bateria FROM expedientes")
    datos = cursor.fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte Mensual"
    
    encabezados = ["Zona", "RPE", "Empleado", "Cat. Actual", "Cat. Impacta", "Evaluación", "Alto Riesgo", "Estatus", "Curso Acreditado", "Cumple Batería"]
    ws.append(encabezados)
    
    for row in datos:
        ws.append(row)
        
    filepath = "reporte_mensual_conoca.xlsx"
    wb.save(filepath)
    return send_file(filepath, as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
    