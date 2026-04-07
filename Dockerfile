FROM odoo:17.0

# On définit l'utilisateur root pour installer des dépendances si besoin
USER root

# On copie tes deux modules dans le dossier addons d'Odoo
COPY ./importation /mnt/extra-addons/importation
# Répète la ligne ci-dessus pour ton deuxième module si son nom est différent
# COPY ./ton_deuxieme_module /mnt/extra-addons/ton_deuxieme_module

# On redonne les droits à l'utilisateur odoo
RUN chown -R odoo /mnt/extra-addons

USER odoo
