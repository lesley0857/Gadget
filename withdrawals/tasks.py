from celery import shared_task

@shared_task
def process_withdrawal(withdrawal_id):
    # call Paystack transfer API
    # debit wallet
    # mark withdrawal as paid
    pass
