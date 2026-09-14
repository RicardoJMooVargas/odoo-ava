FROM odoo:19.0

USER root

COPY ./config/odoo.conf /etc/odoo/odoo.conf
COPY ./addons /mnt/extra-addons

RUN chown -R odoo:odoo /etc/odoo/odoo.conf /mnt/extra-addons \
    && chmod -R 755 /mnt/extra-addons

USER odoo
