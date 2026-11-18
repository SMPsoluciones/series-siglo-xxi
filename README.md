# Series XXI

Las mejores series del siglo XXI, curadas por el Peri: catálogo completo, Infaltables, Unánimes y panel de administración.
Los datos de IMDb (rating, años, temporadas, episodios, póster) vienen de **OMDb** (omdbapi.com)
y el Tomatómetro y la audiencia se leen de la página de **Rotten Tomatoes**.

## Abrir la app

```bash
python -m streamlit run app.py
```

Se abre en http://localhost:8501. El **Admin no aparece en el menú**: entra con
http://localhost:8501/?admin y usa la contraseña de `.streamlit/secrets.toml` (cámbiala ahí cuando quieras).

## Qué hay en la carpeta

| Archivo | Para qué |
|---|---|
| `app.py` | Páginas públicas (Inicio, Colección, Infaltables, Unánimes, Lo último, Sumar una serie). Criterio de Unánimes: `UNAN_PERI`, `UNAN_IMDB`, `UNAN_RT` al inicio del archivo |
| `logo.svg` | Logo de Series XXI |
| `ui.py` | Estilos, tarjetas, ficha y tabla del Top 50 |
| `admin.py` | Panel privado: agregar, recomendaciones, editar, vincular, actualizar, cambios de scores |
| `series.db` | La base de datos con tus series y el historial de scores |
| `fuentes.py` | Consultas a OMDb y Rotten Tomatoes |
| `sincronizar.py` | Vincula series con IMDb y actualiza scores |
| `db.py` | Lectura y escritura de la base |
| `migrar_excel.py` | Carga inicial desde `TOP_SERIES_SIGLOXXI_NUEVA.xlsx` (ya se corrió) |
| `_archivo/` | Scripts, Excels y CSV viejos (no se usan) |

## Actualizar scores sin abrir la app

```bash
python sincronizar.py
```

Opciones: `--limite 100` (solo las 100 con más tiempo sin actualizar) y `--solo-vincular`.
El plan gratis de OMDb permite ~1000 consultas por día.

## Link para compartir

`share/` es la página de entrada que se comparte por WhatsApp (https://series-xxi.vercel.app): tiene la vista previa (`preview.jpg`) y manda a la app. Se publica en Vercel desde esa carpeta con `vercel deploy --prod`.
