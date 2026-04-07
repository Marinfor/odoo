FROM odoo:17.0

USER root
# Copie tout ton dossier actuel dans le dossier addons d'Odoo
COPY . /mnt/extra-addons/
RUN chown -R odoo /mnt/extra-addons

USER odoo
