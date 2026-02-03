"""
python -m scripts.add_jobs
"""

import sys
from datetime import date

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models.job import Job, JobStatus, JobType, PriorityLevel, RecurrenceType, PaymentStatus


def add_jobs():
    """Add jobs to the database."""
    today = date.today()
    tenant_id = 2
    
    jobs_data = [
        ("Ambawadi, Ahmedabad, Gujarat, India", 72.54304379999999, 23.0223701),
        ("old campus, I I M, Vastrapur, Ahmedabad, Gujarat 380015, India", 72.5372217, 23.0325484),
        ("Naranpura, Ahmedabad, Gujarat, India", 72.54970689999999, 23.0521705),
        ("Sector 4/A, Sector 4, Gandhinagar, Gujarat 382006, India", 72.6239764, 23.2069137),
        ("Unjha, Gujarat 384170, India", 72.3902277, 23.8035004),
        ("Siddhpur, Gujarat 384151, India", 72.3621359, 23.9308631),
        ("Dholka, Gujarat 382225, India", 72.4497173, 22.7420906),
    ]
    
    db = SessionLocal()
    
    try:
        for address, lng, lat in jobs_data:
            job = Job(
                tenant_id=tenant_id,
                address_formatted=address,
                status=JobStatus.draft,
                scheduled_date=today,
                job_type=JobType.pickup,
                location=f"POINT({lng} {lat})",
                service_duration=5,
                priority_level=PriorityLevel.medium,
                recurrence_type=RecurrenceType.one_time,
                payment_status=PaymentStatus.paid,
            )
            db.add(job)
            print(f"Added: {address}")
        
        db.commit()
        print(f"\nSuccessfully added {len(jobs_data)} jobs for {today}")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_jobs()
