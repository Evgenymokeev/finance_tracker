from celery import shared_task


@shared_task
def send_expense_notification(expense_id):
    print(f"Expense {expense_id} was created successfully!")

    return f"Expense {expense_id} processed"