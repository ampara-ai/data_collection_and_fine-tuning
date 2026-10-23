# Instalar Poppler en Ubuntu

Para mejorar conversión PDF → imagen con `pdf2image`, instala `poppler-utils`.

## Comando esperado

```bash
sudo apt-get update && sudo apt-get install -y poppler-utils
```

## Binarios que nos interesan

- `pdftoppm`
- `pdftocairo`

## Verificación

```bash
command -v pdftoppm
command -v pdftocairo
pdftoppm -v || true
```

## Nota

El ejecutable **no va al repo**. Solo debe existir en el host.
Mientras no esté instalado, el proyecto puede seguir funcionando con fallback Python en algunos casos, pero la ruta PDF → imagen dependerá de Poppler para ser estable con `pdf2image`.
