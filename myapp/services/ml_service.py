# myapp/services/ml_service.py
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from flask import current_app

def entrenar_modelo():
    try:
        db = current_app.db
        usuarios = list(db.usuarios.find({}, {'_id': 0}))
        if len(usuarios) < 20:
            return None, None

        df = pd.DataFrame(usuarios)
        df = df.where(pd.notnull(df), None)
        
        encoders = {
            'nombre': LabelEncoder().fit(df['nombre'].fillna('')),
            'email': LabelEncoder().fit(df['email'].fillna('')),
            'empresa': LabelEncoder().fit(df['empresa'].fillna('Desconocida')),
            'telefono': LabelEncoder().fit(df['telefono'].fillna('')),
            'motivo visita': LabelEncoder().fit(df['motivo visita'].fillna(''))
        }
        
        X = pd.DataFrame({
            'nombre': encoders['nombre'].transform(df['nombre']),
            'email': encoders['email'].transform(df['email'])
        })
        
        y = encoders['empresa'].transform(df['empresa'])
        
        modelo = RandomForestClassifier(n_estimators=100)
        modelo.fit(X, y)
        
        joblib.dump(modelo, 'modelo_empresas.pkl')
        for campo, encoder in encoders.items():
            joblib.dump(encoder, f'encoder_{campo}.pkl')
        
        return modelo, encoders['empresa']
    except Exception as e:
        print(f"Error entrenando modelo: {e}")
        return None, None
