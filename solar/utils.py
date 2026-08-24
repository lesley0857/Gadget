###############################################################
# solar/services/email_service.py
###############################################################

from django.conf import settings
from django.core.mail import EmailMessage




###############################################################
# SEND DESIGN QUOTATION
###############################################################

def send_design_quotation(

    *, 

    design,

    recipient,

):

    ###########################################################
    # GENERATE PDF
    ###########################################################

    pdf = "lop"


    ###########################################################
    # EMAIL
    ###########################################################

    email = EmailMessage(

        subject=(

            f"Solar Quotation - "

            f"{design.project_name}"

        ),

        body=(

            "Please find attached your solar system quotation."

        ),

        from_email=settings.DEFAULT_FROM_EMAIL,

        to=[

            recipient,

        ],

    )


    ###########################################################
    # ATTACH PDF
    ###########################################################

    email.attach(

        filename=(

            f"{design.project_name}"

            "_quotation.pdf"

        ),

        content=pdf,

        mimetype="application/pdf",

    )


    ###########################################################
    # SEND
    ###########################################################

    email.send(

        fail_silently=False,

    )


    return True