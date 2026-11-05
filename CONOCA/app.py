from flask import Flask, render_template, request, jsonify, session, send_from_directory
import sqlite3
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'conoca_secreto_2026'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solicitudes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zona TEXT,
            rpe TEXT,
            nombre TEXT,
            cat_actual TEXT,
            cat_impacta TEXT,
            evaluacion TEXT,
            alto_riesgo TEXT,
            cumple_bateria TEXT,
            estatus TEXT,
            datos_reg TEXT,
            archivos TEXT,
            docs TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard.html')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    zona = data.get('zona')
    pass_ingresada = data.get('pass')

    passwords_validas = {
        'DJ000': 'DJ000',  # Administrador (Divisionales)
        'DJ010': 'DJ010',  # Poza Rica
        'DJ020': 'DJ020',  # Xalapa
        'DJ030': 'DJ030',  # Teziutlán
        'DJ060': 'DJ060',  # Veracruz
        'DJ070': 'DJ070',  # Papaloapan
        'DJ100': 'DJ100',  # Los Tuxtlas
        'DJ110': 'DJ110',  # Coatzacoalcos
        'DJ130': 'DJ130',  # Orizaba
        'DJ140': 'DJ140'   # Córdoba
    }

    if zona in passwords_validas and passwords_validas[zona] == pass_ingresada:
        session['zona'] = zona
        session['rol'] = 'ADMIN' if zona == 'DJ000' else 'ZONA'
        return jsonify({'success': True, 'rol': session['rol'], 'zona': zona})
    else:
        return jsonify({'success': False, 'error': 'Contraseña incorrecta'}), 401

@app.route('/api/sesion', methods=['GET'])
def get_sesion():
    if 'zona' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    return jsonify({'zona': session['zona'], 'rol': session['rol']})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/solicitudes', methods=['GET', 'POST'])
def gestionar_solicitudes():
    if 'zona' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            zona = session['zona']
            rpe = request.form.get('rpe')
            nombre = request.form.get('nombre')
            cat_actual = request.form.get('catActual')
            cat_impacta = request.form.get('catImpacta')
            evaluacion = request.form.get('tipoEvaluacion')
            alto_riesgo = request.form.get('altoRiesgo')
            cumple_bateria = request.form.get('cumpleBateria')
            
            datos_reg = request.form.get('datosReg', '{}')
            
            nombres_archivos = {}
            for key in request.files:
                file = request.files[key]
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    nombres_archivos[key.replace('file_', '')] = filename

            archivos_json = json.dumps(nombres_archivos)
            num_docs = 3 if evaluacion == 'Teórica' else 4
            docs_iniciales = json.dumps(['Pendiente'] * num_docs)

            cursor.execute('''
                INSERT INTO solicitudes (zona, rpe, nombre, cat_actual, cat_impacta, evaluacion, alto_riesgo, cumple_bateria, estatus, datos_reg, archivos, docs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (zona, rpe, nombre, cat_actual, cat_impacta, evaluacion, alto_riesgo, cumple_bateria, 'En validación', datos_reg, archivos_json, docs_iniciales))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'mensaje': 'Solicitud registrada correctamente'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'error': str(e)}), 500

    rol = session['rol']
    zona_actual = session['zona']
    zona_filtro = request.args.get('zona', 'TODAS')

    if rol == 'ADMIN':
        if zona_filtro != 'TODAS':
            cursor.execute('SELECT id, zona, rpe, nombre, cat_actual, cat_impacta, evaluacion, alto_riesgo, cumple_bateria, estatus, datos_reg, archivos, docs FROM solicitudes WHERE zona = ?', (zona_filtro,))
        else:
            cursor.execute('SELECT id, zona, rpe, nombre, cat_actual, cat_impacta, evaluacion, alto_riesgo, cumple_bateria, estatus, datos_reg, archivos, docs FROM solicitudes')
    else:
        cursor.execute('SELECT id, zona, rpe, nombre, cat_actual, cat_impacta, evaluacion, alto_riesgo, cumple_bateria, estatus, datos_reg, archivos, docs FROM solicitudes WHERE zona = ?', (zona_actual,))

    rows = cursor.fetchall()
    conn.close()

    resultado = []
    for row in rows:
        resultado.append({
            'id': row[0],
            'zona': row[1],
            'rpe': row[2],
            'nombre': row[3],
            'catActual': row[4],
            'catImpacta': row[5],
            'evaluacion': row[6],
            'alto_riesgo': row[7],
            'cumpleBateria': row[8],
            'estatus': row[9],
            'datosReg': json.loads(row[10]) if row[10] else {},
            'archivos': json.loads(row[11]) if row[11] else {},
            'docs': json.loads(row[12]) if row[12] else []
        })

    return jsonify(resultado)

@app.route('/api/validar/<int:id>', methods=['POST'])
def validar_solicitud(id):
    if session.get('rol') != 'ADMIN':
        return jsonify({'error': 'Acceso denegado'}), 403

    data = request.json
    nuevos_docs = data.get('docs', [])
    
    todos_cumplen = all(d == 'Cumple' for d in nuevos_docs)
    algun_rechazado = any(d == 'No cumple' for d in nuevos_docs)

    estatus = 'Cumple' if todos_cumplen else ('No cumple' if algun_rechazado else 'En validación')

    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE solicitudes SET docs = ?, estatus = ? WHERE id = ?', (json.dumps(nuevos_docs), estatus, id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'estatus': estatus})

@app.route('/api/actualizar_archivo/<int:id>', methods=['POST'])
def actualizar_archivo(id):
    if 'zona' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    cursor.execute('SELECT zona, archivos, docs FROM solicitudes WHERE id = ?', (id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'No encontrado'}), 404

    zona_solicitud = row[0]
    archivos_actuales = json.loads(row[1]) if row[1] else {}
    docs_actuales = json.loads(row[2]) if row[2] else []

    if session['rol'] != 'ADMIN' and session['zona'] != zona_solicitud:
        conn.close()
        return jsonify({'error': 'No autorizado'}), 403

    # Guardar nuevo archivo subido
    for key in request.files:
        file = request.files[key]
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # Identificar qué archivo se está actualizando (ej. examenTeorico, evidenciaFoto, dc3, etc.)
            doc_key = key.replace('file_', '')
            archivos_actuales[doc_key] = filename

            # Al actualizar el archivo, el estatus de ese documento específico regresa a 'Pendiente' para nueva revisión del Admin
            mapeo_indices = {'examenTeorico': 0, 'examenPractico': 1, 'evidenciaFoto': 2 if len(docs_actuales)>3 else 1, 'dc3': len(docs_actuales)-1}
            idx = mapeo_indices.get(doc_key, 0)
            if idx < len(docs_actuales):
                docs_actuales[idx] = 'Pendiente'

    cursor.execute('UPDATE solicitudes SET archivos = ?, docs = ?, estatus = ? WHERE id = ?', 
                   (json.dumps(archivos_actuales), json.dumps(docs_actuales), 'En validación', id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'mensaje': 'Archivo actualizado correctamente'})

@app.route('/api/solicitudes/<int:id>', methods=['DELETE'])
def eliminar_solicitud(id):
    if 'zona' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    conn = sqlite3.connect('conoca.db')
    cursor = conn.cursor()
    
    # Validar que la zona solo borre lo suyo (a menos que sea ADMIN)
    cursor.execute('SELECT zona FROM solicitudes WHERE id = ?', (id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'No encontrado'}), 404

    if session['rol'] != 'ADMIN' and session['zona'] != row[0]:
        conn.close()
        return jsonify({'error': 'No autorizado'}), 403

    cursor.execute('DELETE FROM solicitudes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/uploads/<path:filename>')
def ver_archivo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
    