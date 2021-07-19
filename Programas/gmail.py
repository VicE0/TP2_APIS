#MODULOS PROPIOS DE PYTHON
import os
import datetime
import time
import csv

import base64
from typing import List
#modulos para la API
from googleapiclient.discovery import Resource, build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64

from pathlib import Path

#constantes
ASUNTO = 20
EMAIL = 1
ARCHIVO_ADJUNTO = 1
ORIGEN = 17
ARCHIVO_SECRET_CLIENT = 'client_secret_gmail.json'

RUTA_CARPETA = "EVALUACIONES"
RUTA_ENTREGAS_ALUMNOS = f"{Path.home()}/Desktop/{RUTA_CARPETA}/"

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]


def cargar_credenciales() -> Credentials:
    credencial = None

    if os.path.exists('token.json'):
        with open('token.json', 'r'):
            credencial = Credentials.from_authorized_user_file('token.json', SCOPES)

    return credencial


def guardar_credenciales(credencial: Credentials) -> None:
    with open('token.json', 'w') as token:
        token.write(credencial.to_json())


def son_credenciales_invalidas(credencial: Credentials) -> bool:
    return not credencial or not credencial.valid


def son_credenciales_expiradas(credencial: Credentials) -> bool:
    return credencial and credencial.expired and credencial.refresh_token


def autorizar_credenciales() -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(ARCHIVO_SECRET_CLIENT, SCOPES)

    return flow.run_local_server(open_browser=False, port=0)


def generar_credenciales() -> Credentials:
    credencial = cargar_credenciales()

    if son_credenciales_invalidas(credencial):

        if son_credenciales_expiradas(credencial):
            credencial.refresh(Request())

        else:
            credencial = autorizar_credenciales()

        guardar_credenciales(credencial)

    return credencial


def obtener_servicio() -> Resource:
    """
    Creador de la conexion a la API Gmail
    """
    return build('gmail', 'v1', credentials=generar_credenciales())

'''
Todo lo anterior a la variable servicio se encuentra en el archivo conexion_gmail, se debe importar, pero
estoy teniendo problemas para importarlos, no me reconoce la ruta, lo solucionare.
'''


def obtener_datos_mails(id_mails:list, servicio:Resource) -> dict:

    #PRE: Recibimos la lista con los id de los mails que coinciden con la fecha actual.
    #POST: Retornamos un diccionario con los datos que requerimos obtener de estos mails enviados.

    datos_emails = {} #{id de mail:{"asunto":asunto, "origen":origen, "id de archivo adjunto":id_archivo_adjunto}}

    for id_mail in id_mails:

        lectura_mail = servicio.users().messages().get(userId='evaluaciontp2@gmail.com', id = id_mail).execute()

        for i in lectura_mail['payload']['headers']:
            if i['name'] == "From":
                origen = lectura_mail['payload']['headers'].index(i)
            if i['name'] == "Subject":
                asunto = lectura_mail['payload']['headers'].index(i)

        datos_origen = lectura_mail['payload']['headers'][origen]['value'].split("<")
        email_origen = datos_origen[EMAIL].rstrip(">")
        asunto = lectura_mail['payload']['headers'][asunto]['value'].split("-")
        id_archivo_adjunto = lectura_mail['payload']['parts'][ARCHIVO_ADJUNTO]['body']['attachmentId']
        datos_emails[id_mail] = {"asunto":asunto, "origen": email_origen, "adj_id":id_archivo_adjunto}

    return datos_emails


def obtener_ids_mails(servicio:Resource, fecha_actual:int) -> list:

    #PRE: No recibimos ningun parametro.
    #POST: Retronamos en una lista los id's de los mails.
    
    id_mails = []
    try:
        emails_recibidos = servicio.users().messages().list(userId='evaluaciontp2@gmail.com', 
                                                            q=f'before: {fecha_actual} label: inbox').execute()

        obteniendo_ids = emails_recibidos['messages']

        for id in obteniendo_ids:

            id_mails.append(id['id'])

    except KeyError:
        print("No hay mensajes de evaluaciones para revisar hoy")

    return id_mails


def obtener_fecha_actual() -> int:

    #PRE: No recibimos nada como argumento
    #POST: Retornamos la fecha casteada como int en formato UNIX

    fecha = str(datetime.date.today())
    conversion_unix = int(time.mktime(datetime.datetime.strptime(fecha.replace("-","/"), '%Y/%m/%d').timetuple()))

    return conversion_unix


def validar_padron_alumnos(id_mails:list, datos_emails:dict, servicio:Resource,
                            emails_entregas_correctas:list, emails_entregas_incorrectas:list) -> dict:

    #PRE:Recibimos los ids de mails(lista) y datos correspondientes a esos ids de mails(diccionario).
    #POST: Una vez validado el padron se retorna un diccionario con los datos de entregas correctas.

    lineas_archivo_csv = []
    datos_entregas_correctas = {}
    validando_padrones = False

    with open(f"{RUTA_ENTREGAS_ALUMNOS}/alumnos.csv", "r") as archivo:

        lectura_archivo_alumnos = csv.reader(archivo, delimiter=';')
        next(lectura_archivo_alumnos)

        for linea in lectura_archivo_alumnos:
            lineas_archivo_csv.append(linea)               

        for id_mail in id_mails:
            k = 0

            while k < 17:

                if datos_emails[id_mail]['asunto'][0].strip(" ") in lineas_archivo_csv[k][1]:
                    emails_entregas_correctas.append(datos_emails[id_mail]['origen'])
                    datos_entregas_correctas[id_mail] = {"id_adjunto":datos_emails[id_mail]['adj_id']}
                    k = 17

                else:                  
                    if k < 16:
                        if not validando_padrones:
                            print("validando padrones")
                            validando_padrones = True
                    else:
                        emails_entregas_incorrectas.append(datos_emails[id_mail]['origen'])
                    k+=1

    return datos_entregas_correctas


def enviar_mails(servicio:Resource, entregas:list, asunto:str, cuerpo:str) -> None:

    #PRE: Recibimos una lista con los emails de alumnos que tienen una entrega exitosa o fallida.
    #POST: Se envian los mails correspondientes a esos alumnos.
    
    if len(entregas) == 0:

        print(f"\n\nNo hay {asunto} que actualizar via mail") 

    else:

        for mail in entregas:

            mensaje_email = cuerpo
            mimeMessage = MIMEMultipart()
            mimeMessage["to"] = mail
            mimeMessage["subject"] = asunto  
            mimeMessage.attach(MIMEText(mensaje_email, "plain"))
            decodificando_mensaje = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()

            mensaje = servicio.users().messages().send(userId = "evaluaciontp2@gmail.com", 
                                                        body = {"raw": decodificando_mensaje}).execute()

            print(f"Mensaje de {asunto} enviado! :)")


def obtener_archivos_adjuntos(servicio:Resource, datos_entrega_correcta:dict, datos_emails:dict) -> list:

    #PRE: Recibimos como diccionarios las entregas correctas y los datos de los mails.
    #POST: Una vez obtenido el archivo adjunto, se retorna el nombre de ls archivos adjuntos como lista.

    nombres_archivos_creados = []
    id_mails = []
    
    for id_mail in datos_entrega_correcta:
        id_mails.append(id_mail)

    for id in id_mails:
        nombres_archivos_creados.append("".join(datos_emails[id]['asunto']))

    for indice in range(len(id_mails)):

        archivo_adjunto = servicio.users().messages().attachments().get(userId='evaluaciontp2@gmail.com',
                        messageId=id_mails[indice], id=datos_entrega_correcta[id_mails[indice]]['id_adjunto']).execute()
        
        data_archivo_adjunto = archivo_adjunto['data']
        decodificando_archivo_adjunto = base64.urlsafe_b64decode(data_archivo_adjunto.encode('UTF-8'))
        
        try:
            os.makedirs(f'{RUTA_ENTREGAS_ALUMNOS}/ENTREGAS_ALUMNOS')
        except FileExistsError:
            pass

        with open(
        f"{RUTA_ENTREGAS_ALUMNOS}/ENTREGAS_ALUMNOS/{nombres_archivos_creados[indice]}.zip", "wb") as archivo:
            archivo.write(decodificando_archivo_adjunto)
        
    return nombres_archivos_creados


def main(emails_entregas_correctas:list, emails_entregas_incorrectas) -> list:

    fecha = obtener_fecha_actual()
    servicio = obtener_servicio()
    id_mails = obtener_ids_mails(servicio, fecha)
    if len(id_mails) == 0:
        nombres_archivos_adjuntos = []
    else:
        datos_emails = obtener_datos_mails(id_mails, servicio)
        datos_entregas_correctas = validar_padron_alumnos(id_mails, datos_emails, servicio, 
                                                        emails_entregas_correctas, emails_entregas_incorrectas)

        nombres_archivos_adjuntos = obtener_archivos_adjuntos(servicio, datos_entregas_correctas, datos_emails)

    return nombres_archivos_adjuntos