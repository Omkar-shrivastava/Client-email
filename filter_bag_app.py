"""
Filter Bag Specification System - Complete Flask Application
Features: Email sender, Form receiver, PostgreSQL Database, PO Number Management, Admin Login
"""

from flask import Flask, render_template_string, request, jsonify, url_for, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import requests
import secrets
import os
import socket

socket.setdefaulttimeout(10)

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")

# ==================== PostgreSQL CONFIG ====================
# Set DATABASE_URL in environment: postgresql://user:password@host:port/dbname
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:omkar123@localhost:5432/filter_bags"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Database
db = SQLAlchemy(app)

SENDER_EMAIL   = os.environ.get("SENDER_EMAIL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

# ==================== ADMIN CREDENTIALS ====================
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")   # Change this!

# ==================== DATABASE MODELS ====================

class FilterBagSubmission(db.Model):
    __tablename__ = 'filter_bag_submissions'

    id               = db.Column(db.Integer, primary_key=True)
    token            = db.Column(db.String(100), nullable=False, index=True)
    recipient_email  = db.Column(db.String(200), nullable=False)
    po_number        = db.Column(db.String(100))

    bag_type         = db.Column(db.String(50))

    collar_od        = db.Column(db.String(100))
    collar_id        = db.Column(db.String(100))
    tubesheet_data   = db.Column(db.Text)
    tubesheet_dia    = db.Column(db.String(100))

    client_name      = db.Column(db.String(200))
    client_email     = db.Column(db.String(200))
    quantity         = db.Column(db.Integer)
    delivery_date    = db.Column(db.String(50))
    remarks          = db.Column(db.Text)

    submitted        = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at     = db.Column(db.DateTime)

    admin_quantity   = db.Column(db.Integer)
    admin_size       = db.Column(db.String(200))
    superseded       = db.Column(db.Boolean, default=False)  # True = purana record, naya aa gaya

    def __repr__(self):
        return f'<Submission {self.id} - {self.recipient_email}>'


class BagSize(db.Model):
    __tablename__ = 'bag_sizes'

    id         = db.Column(db.Integer, primary_key=True)
    size_name  = db.Column(db.String(100), nullable=False)
    bag_type   = db.Column(db.String(50),  nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<BagSize {self.size_name} - {self.bag_type}>'


with app.app_context():
    db.create_all()


# ==================== ADMIN AUTH ====================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session.permanent = False
            return redirect(url_for('sender_page'))
        else:
            error = "Invalid username or password."
    return render_template_string(LOGIN_HTML, error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


# ==================== HELPER ====================

def get_parent_submission(token):
    parent = FilterBagSubmission.query.filter_by(
        token=token, bag_type=None
    ).order_by(FilterBagSubmission.id.asc()).first()
    if parent:
        return parent
    return FilterBagSubmission.query.filter_by(
        token=token
    ).order_by(FilterBagSubmission.id.asc()).first()


# ==================== EMAIL FUNCTIONS ====================

def send_email_resend(to_email, subject, html_body):
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": f"Vaayushanti <{SENDER_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body
        }
        response = requests.post(url, json=payload, headers=headers)
        print("📩 RESEND RESPONSE:", response.status_code, response.text)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ RESEND ERROR: {str(e)}")
        return False


def send_form_email(recipient_email, token, po_number=None):
    try:
        form_url = url_for('filter_form', token=token, _external=True)
        po_info  = f"<p><strong>PO Number:</strong> {po_number}</p>" if po_number else ""
        subject  = "🔧 Filter Bag Specification Request"
        html_body = f"""
        <!DOCTYPE html><html><head>
        <style>
            body{{font-family:Arial,sans-serif;line-height:1.6;color:#333;}}
            .container{{max-width:600px;margin:0 auto;padding:20px;}}
            .header{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0;}}
            .content{{background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px;}}
            .button{{display:inline-block;padding:15px 30px;background:#667eea;color:white;text-decoration:none;border-radius:5px;margin:20px 0;}}
            .footer{{text-align:center;margin-top:20px;color:#666;font-size:12px;}}
        </style></head><body>
        <div class="container">
            <div class="header"><h1>🔧 Filter Bag Specification Request</h1><p>We need your filter bag specifications</p></div>
            <div class="content">
                <p>Dear Valued Client,</p>
                <p>To proceed with your order, we kindly request you to share the filter bag specifications.</p>
                {po_info}
                <center><a href="{form_url}" class="button">📋 Fill Specification Form</a></center>
                <p><strong>Note:</strong> This link is unique to you. You can use it to fill or edit your specifications.</p>
            </div>
            <div class="footer"><p><strong>Filter Bag Specification System</strong></p><p>Contact: {SENDER_EMAIL}</p></div>
        </div></body></html>
        """
        return send_email_resend(recipient_email, subject, html_body)
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


def send_submission_notification(submissions_list):
    try:
        first = submissions_list[0]
        bag_count = len(submissions_list)
        subject = f"✅ Form Submitted - {first.client_name or 'Client'} ({bag_count} bag{'s' if bag_count > 1 else ''})"

        bags_details = ""
        for idx, s in enumerate(submissions_list, 1):
            spec = ""
            if s.bag_type == 'collar':
                spec = f"<tr><td><strong>Collar OD:</strong></td><td>{s.collar_od}</td></tr><tr><td><strong>Collar ID:</strong></td><td>{s.collar_id}</td></tr>"
            elif s.bag_type == 'snap':
                spec = f"<tr><td><strong>Tubesheet Data:</strong></td><td>{s.tubesheet_data}</td></tr>"
            elif s.bag_type == 'ring':
                spec = f"<tr><td><strong>Tubesheet Diameter:</strong></td><td>{s.tubesheet_dia}</td></tr>"
            bags_details += f"""
            <h4 style="color:#1f3c88;margin-top:20px;">🛍️ Bag #{idx} - {s.bag_type.title() if s.bag_type else 'N/A'}</h4>
            <table style="width:100%;border-collapse:collapse;margin:10px 0;">
                <tr><td style="padding:8px;border-bottom:1px solid #ddd;"><strong>Bag Type:</strong></td><td style="padding:8px;border-bottom:1px solid #ddd;">{s.bag_type.title() if s.bag_type else 'N/A'}</td></tr>
                {spec}
                <tr><td style="padding:8px;border-bottom:1px solid #ddd;"><strong>Quantity:</strong></td><td style="padding:8px;border-bottom:1px solid #ddd;">{s.quantity or 'N/A'}</td></tr>
            </table>"""

        html_body = f"""<!DOCTYPE html><html><head>
        <style>
            body{{font-family:Arial,sans-serif;line-height:1.6;color:#333;}}
            .container{{max-width:700px;margin:0 auto;padding:20px;}}
            .header{{background:linear-gradient(135deg,#11998e 0%,#38ef7d 100%);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0;}}
            .content{{background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px;}}
            table{{width:100%;border-collapse:collapse;margin:20px 0;}}
            td{{padding:10px;border-bottom:1px solid #ddd;}}
            .footer{{text-align:center;margin-top:20px;color:#666;font-size:12px;}}
        </style></head><body>
        <div class="container">
            <div class="header"><h1>✅ Form Submitted Successfully</h1></div>
            <div class="content">
                <h3>📋 Client Details:</h3>
                <table>
                    <tr><td><strong>Client Name:</strong></td><td>{first.client_name}</td></tr>
                    <tr><td><strong>Client Email:</strong></td><td>{first.client_email}</td></tr>
                    <tr><td><strong>PO Number:</strong></td><td>{first.po_number or 'N/A'}</td></tr>
                    <tr><td><strong>Quantity:</strong></td><td>{first.admin_quantity or 'N/A'}</td></tr>
                    <tr><td><strong>Size:</strong></td><td>{first.admin_size or 'N/A'}</td></tr>
                    <tr><td><strong>Total Bags:</strong></td><td>{bag_count}</td></tr>
                    <tr><td><strong>Submitted At:</strong></td><td>{first.submitted_at.strftime('%d %b %Y, %I:%M %p') if first.submitted_at else 'N/A'}</td></tr>
                </table>
                <h3>🛍️ Bag Specifications:</h3>
                {bags_details}
                <p><strong>Remarks:</strong><br>{first.remarks or 'No additional remarks'}</p>
            </div>
            <div class="footer"><p>Filter Bag Specification System — Automated notification</p></div>
        </div></body></html>"""

        return send_email_resend(SENDER_EMAIL, subject, html_body)
    except Exception as e:
        print(f"❌ Error sending notification: {str(e)}")
        return False


def send_client_submission_notification(submissions_list):
    try:
        first = submissions_list[0]
        bag_count = len(submissions_list)
        form_url = url_for('filter_form', token=first.token, _external=True)
        subject = f"✅ Your Filter Bag Submission Details ({bag_count} Bag{'s' if bag_count > 1 else ''})"

        bags_details = ""
        for idx, s in enumerate(submissions_list, 1):
            spec = ""
            if s.bag_type == 'collar':
                spec = f"<tr><td><strong>Collar OD:</strong></td><td>{s.collar_od}</td></tr><tr><td><strong>Collar ID:</strong></td><td>{s.collar_id}</td></tr>"
            elif s.bag_type == 'snap':
                spec = f"<tr><td><strong>Tubesheet Data:</strong></td><td>{s.tubesheet_data}</td></tr>"
            elif s.bag_type == 'ring':
                spec = f"<tr><td><strong>Tubesheet Diameter:</strong></td><td>{s.tubesheet_dia}</td></tr>"
            bags_details += f"""
            <h4 style="color:#1f3c88;margin-top:20px;">🛍️ Bag #{idx} - {s.bag_type.title()}</h4>
            <table style="width:100%;border-collapse:collapse;margin:10px 0;">
                <tr><td><strong>Bag Type:</strong></td><td>{s.bag_type.title()}</td></tr>
                {spec}
                <tr><td><strong>Quantity:</strong></td><td>{s.quantity}</td></tr>
            </table>"""

        html_body = f"""<!DOCTYPE html><html><head>
        <style>
            body{{font-family:Arial,sans-serif;line-height:1.6;}}
            .container{{max-width:700px;margin:0 auto;padding:20px;}}
            .header{{background:#1e5aa8;color:white;padding:25px;text-align:center;border-radius:10px 10px 0 0;}}
            .content{{background:#f9f9f9;padding:30px;border-radius:0 0 10px 10px;}}
            table{{width:100%;border-collapse:collapse;margin:15px 0;}}
            td{{padding:8px;border-bottom:1px solid #ddd;}}
            .edit-btn{{display:inline-block;padding:12px 25px;background:#1e5aa8;color:white;text-decoration:none;border-radius:5px;margin-top:20px;}}
        </style></head><body>
        <div class="container">
            <div class="header"><h2>✅ Thank You for Your Submission</h2></div>
            <div class="content">
                <p>Your filter bag specification has been successfully submitted.</p>
                <table>
                    <tr><td><strong>PO Number:</strong></td><td>{first.po_number or 'N/A'}</td></tr>
                    <tr><td><strong>Quantity:</strong></td><td>{first.admin_quantity or 'N/A'}</td></tr>
                    <tr><td><strong>Size:</strong></td><td>{first.admin_size or 'N/A'}</td></tr>
                    <tr><td><strong>Total Bags Submitted:</strong></td><td>{bag_count}</td></tr>
                </table>
                <h3>📋 Submission Details</h3>
                {bags_details}
                <p><strong>Overall Remarks:</strong><br>{first.remarks or 'No additional remarks'}</p>
                <a href="{form_url}" class="edit-btn">✏️ Edit &amp; Re-Submit Form</a>
            </div>
        </div></body></html>"""

        return send_email_resend(first.recipient_email, subject, html_body)
    except Exception as e:
        print(f"❌ Error sending client notification: {str(e)}")
        return False


# ==================== ROUTES ====================

@app.route('/')
@app.route('/sender')
@login_required
def sender_page():
    return render_template_string(SENDER_HTML)


@app.route('/api/send-form', methods=['POST'])
@login_required
def send_form():
    try:
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data'}), 400

        recipient_email = data.get('recipient_email', '').strip()
        po_number       = data.get('po_number', '').strip()
        admin_quantity  = data.get('admin_quantity')
        admin_size      = data.get('admin_size', '').strip()

        if not recipient_email:
            return jsonify({'success': False, 'message': 'Please provide recipient email'}), 400
        if not admin_quantity or not admin_size:
            return jsonify({'success': False, 'message': 'Please provide Quantity and Size'}), 400

        try:
            admin_quantity = int(admin_quantity)
            if admin_quantity <= 0:
                raise ValueError
        except ValueError:
            return jsonify({'success': False, 'message': 'Quantity must be a valid positive number'}), 400

        token = secrets.token_urlsafe(32)
        submission = FilterBagSubmission(
            token=token,
            recipient_email=recipient_email,
            po_number=po_number if po_number else None,
            admin_quantity=admin_quantity,
            admin_size=admin_size
        )
        db.session.add(submission)
        db.session.commit()

        email_sent = send_form_email(recipient_email, token, po_number)

        if email_sent:
            return jsonify({
                'success': True,
                'message': f'Form link sent successfully to {recipient_email}!' + (f' (PO: {po_number})' if po_number else ''),
                'form_url': url_for('filter_form', token=token, _external=True)
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to send email. Please check email settings.'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/generate-link', methods=['POST'])
@login_required
def generate_link():
    try:
        data           = request.get_json(silent=True) or {}
        po_number      = data.get('po_number', '').strip()
        admin_quantity = data.get('admin_quantity')
        admin_size     = data.get('admin_size', '').strip()

        if not admin_quantity or not admin_size:
            return jsonify({'success': False, 'message': 'Please provide Quantity and Size'}), 400

        try:
            admin_quantity = int(admin_quantity)
            if admin_quantity <= 0:
                raise ValueError
        except ValueError:
            return jsonify({'success': False, 'message': 'Quantity must be a valid positive number'}), 400

        token = secrets.token_urlsafe(32)
        submission = FilterBagSubmission(
            token=token,
            recipient_email='direct-link-generated',
            po_number=po_number if po_number else None,
            admin_quantity=admin_quantity,
            admin_size=admin_size
        )
        db.session.add(submission)
        db.session.commit()

        form_url = url_for('filter_form', token=token, _external=True)
        return jsonify({
            'success': True,
            'message': 'Form link generated successfully!' + (f' (PO: {po_number})' if po_number else ''),
            'form_url': form_url
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/form/<token>')
def filter_form(token):
    submission = get_parent_submission(token)
    if not submission:
        return """
        <div style='text-align:center;padding:50px;font-family:Arial;'>
            <h2>❌ Invalid or expired form link</h2>
            <p>This form link is not valid. Please contact the sender for a new link.</p>
        </div>
        """, 404
    return render_template_string(
        FILTER_FORM_HTML,
        token=token,
        recipient_email=submission.recipient_email,
        po_number=submission.po_number,
        admin_quantity=submission.admin_quantity,
        admin_size=submission.admin_size
    )


@app.route('/api/submit-form/<token>', methods=['POST'])
def submit_form(token):
    try:
        parent_submission = get_parent_submission(token)
        if not parent_submission:
            return jsonify({'success': False, 'message': 'Invalid form link. Please request a new link from the sender.'}), 404

        data = request.get_json(silent=True) or {}
        bags = data.get('bags', [])

        if not bags:
            return jsonify({'success': False, 'message': 'Please add bag specification'}), 400

        # ✅ FIX: Delete mat karo — purane records ko superseded mark karo
        # Taaki history preserve rahe aur koi data na jaye
        old_records = FilterBagSubmission.query.filter(
            FilterBagSubmission.token == token,
            FilterBagSubmission.bag_type.isnot(None)
        ).all()
        for old in old_records:
            old.superseded = True
        db.session.flush()

        bag = bags[0]
        bag_submission = FilterBagSubmission(
            token=token,
            recipient_email=parent_submission.recipient_email,
            po_number=parent_submission.po_number,
            admin_quantity=parent_submission.admin_quantity,
            admin_size=parent_submission.admin_size,
            bag_type=bag.get('bag_type'),
            collar_od=bag.get('collar_od'),
            collar_id=bag.get('collar_id'),
            tubesheet_data=bag.get('tubesheet_data'),
            tubesheet_dia=bag.get('tubesheet_dia'),
            client_name=bag.get('client_name'),
            client_email=bag.get('client_email'),
            quantity=parent_submission.admin_quantity,
            delivery_date=None,
            remarks=data.get('global_remarks'),
            submitted=True,
            submitted_at=datetime.utcnow()
        )
        db.session.add(bag_submission)

        parent_submission.submitted    = True
        parent_submission.submitted_at = datetime.utcnow()
        db.session.commit()

        send_submission_notification([bag_submission])
        send_client_submission_notification([bag_submission])

        return jsonify({'success': True, 'message': 'Successfully submitted bag specification! Thank you for your response.', 'bags_count': 1})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error submitting form: {str(e)}'}), 500


@app.route('/submissions')
@login_required
def view_submissions():
    # ✅ FIX: Sirf actual bag submissions dikhao (bag_type wale records)
    # Parent records (bag_type=None) sirf internal tracking ke liye hain
    # Superseded (purane) records bhi dikhao history ke liye — latest pehle
    submissions = FilterBagSubmission.query.filter(
        FilterBagSubmission.bag_type.isnot(None)
    ).order_by(
        FilterBagSubmission.submitted_at.desc().nullslast(),
        FilterBagSubmission.created_at.desc()
    ).all()
    return render_template_string(SUBMISSIONS_HTML, submissions=submissions)


@app.route('/api/sizes', methods=['POST'])
@login_required
def add_size():
    try:
        data      = request.get_json(silent=True) or {}
        size_name = data.get('size_name', '').strip()
        bag_type  = data.get('bag_type', '').strip()

        if not size_name or not bag_type:
            return jsonify({'success': False, 'message': 'Size name and bag type required'}), 400

        existing = BagSize.query.filter_by(size_name=size_name, bag_type=bag_type).first()
        if existing:
            return jsonify({'success': False, 'message': 'This size already exists'}), 400

        new_size = BagSize(size_name=size_name, bag_type=bag_type)
        db.session.add(new_size)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Size "{size_name}" added successfully',
                        'size': {'id': new_size.id, 'size_name': new_size.size_name, 'bag_type': new_size.bag_type}})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/sizes/<bag_type>', methods=['GET'])
def get_sizes(bag_type):
    try:
        sizes = BagSize.query.filter_by(bag_type=bag_type).order_by(BagSize.created_at.desc()).all()
        return jsonify({'success': True, 'sizes': [{'id': s.id, 'size_name': s.size_name} for s in sizes]})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/sizes/<int:size_id>', methods=['DELETE'])
@login_required
def delete_size(size_id):
    try:
        size = db.session.get(BagSize, size_id)
        if not size:
            return jsonify({'success': False, 'message': 'Size not found'}), 404
        db.session.delete(size)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Size deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ==================== HTML TEMPLATES ====================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login — Filter Bag System</title>
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1f3c88 0%, #667eea 50%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 25px 60px rgba(0,0,0,0.35);
            width: 100%;
            max-width: 420px;
            overflow: hidden;
        }
        .card-header {
            background: linear-gradient(135deg, #1f3c88 0%, #667eea 100%);
            padding: 40px 35px 30px;
            text-align: center;
            color: white;
        }
        .lock-icon {
            font-size: 3rem;
            margin-bottom: 12px;
            display: block;
        }
        .card-header h1 {
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .card-header p {
            font-size: 0.9rem;
            opacity: 0.85;
        }
        .card-body { padding: 35px; }
        .form-group { margin-bottom: 22px; }
        .form-group label {
            display: block;
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        .input-wrapper { position: relative; }
        .input-wrapper span {
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 1.1rem;
            pointer-events: none;
        }
        .input-wrapper input {
            width: 100%;
            padding: 13px 14px 13px 42px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 15px;
            transition: all 0.3s;
            font-family: inherit;
        }
        .input-wrapper input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.15);
        }
        .error-box {
            background: #fef0f0;
            border: 1.5px solid #f5c6cb;
            color: #721c24;
            padding: 12px 16px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .login-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #1f3c88 0%, #667eea 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            letter-spacing: 0.5px;
        }
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102,126,234,0.4);
        }
        .login-btn:active { transform: translateY(0); }
        .card-footer {
            background: #f7f8ff;
            padding: 16px 35px;
            text-align: center;
            font-size: 0.8rem;
            color: #888;
            border-top: 1px solid #eee;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="lock-icon">🔐</span>
            <h1>Admin Login</h1>
            <p>Filter Bag Specification System</p>
        </div>
        <div class="card-body">
            {% if error %}
            <div class="error-box">❌ {{ error }}</div>
            {% endif %}
            <form method="POST" action="/admin/login">
                <div class="form-group">
                    <label for="username">Username</label>
                    <div class="input-wrapper">
                        <span>👤</span>
                        <input type="text" id="username" name="username" placeholder="Enter admin username" required autofocus>
                    </div>
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <div class="input-wrapper">
                        <span>🔑</span>
                        <input type="password" id="password" name="password" placeholder="Enter admin password" required>
                    </div>
                </div>
                <button type="submit" class="login-btn">🚀 Login to Dashboard</button>
            </form>
        </div>
        <div class="card-footer">
            Vaayushanti Solutions Pvt Ltd &nbsp;|&nbsp; Secure Admin Access
        </div>
    </div>
</body>
</html>
"""

SENDER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Send Filter Bag Form</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; position: relative; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .logout-btn { position: absolute; top: 20px; right: 20px; background: rgba(255,255,255,0.2); color: white; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600; transition: all 0.3s; border: 1.5px solid rgba(255,255,255,0.4); }
        .logout-btn:hover { background: rgba(255,255,255,0.35); }
        .content { padding: 40px; }
        .info-box { background: #e3f2fd; padding: 20px; border-radius: 10px; margin-bottom: 30px; border-left: 5px solid #2196F3; }
        .form-group { margin-bottom: 25px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #333; }
        input { width: 100%; padding: 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; transition: all 0.3s; font-family: inherit; }
        input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .btn { width: 100%; padding: 18px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .link-btn { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); margin-top: 15px; }
        .message { padding: 15px; border-radius: 8px; margin-bottom: 20px; display: none; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .footer { text-align: center; padding: 20px; background: #f5f5f5; color: #666; }
        .view-link { display: inline-block; margin-top: 20px; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; transition: all 0.3s; }
        .view-link:hover { background: #764ba2; transform: translateY(-2px); }
        .generated-link { background: #f0f7ff; padding: 15px; border-radius: 8px; margin-top: 15px; word-break: break-all; display: none; }
        .copy-btn { background: #667eea; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; margin-top: 10px; }
        .tabs { display: flex; margin-bottom: 20px; border-bottom: 2px solid #ddd; }
        .tab { flex: 1; padding: 15px; text-align: center; cursor: pointer; background: #f5f5f5; border: none; font-size: 16px; font-weight: 600; transition: all 0.3s; }
        .tab.active { background: white; color: #667eea; border-bottom: 3px solid #667eea; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        select { cursor: pointer; width: 100%; padding: 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; transition: all 0.3s; font-family: inherit; }
        select:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .po-config-box { background:#fff3cd; padding:20px; border-radius:10px; margin-bottom:30px; border-left:5px solid #ffc107; }
        .po-config-box h3 { margin-bottom:15px; color:#856404; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="/admin/logout" class="logout-btn">🚪 Logout</a>
            <h1>📧 Send Filter Bag Form</h1>
            <p>Send specification form to your clients</p>
        </div>

        <div class="content">
            <div class="info-box">
                <strong>ℹ️ How it works:</strong>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li><strong>Send via Email:</strong> Enter client email. They'll receive an email with the form link.</li>
                    <li><strong>Generate Link:</strong> Create a shareable form link without sending an email.</li>
                </ul>
            </div>

            <div class="tabs">
                <button class="tab active" onclick="switchTab('email', event)">📧 Send via Email</button>
                <button class="tab" onclick="switchTab('link', event)">🔗 Generate Link</button>
                <button class="tab" onclick="switchTab('sizes', event)">📏 Manage Sizes</button>
            </div>

            <!-- EMAIL TAB -->
            <div id="emailTab" class="tab-content active">
                <div id="emailMessage" class="message"></div>
                <div class="po-config-box">
                    <h3>📦 PO Configuration</h3>
                    <div class="form-group">
                        <label>📋 PO Number</label>
                        <input type="text" id="poNumber" placeholder="Enter PO Number (e.g., PO-2026-001)">
                    </div>
                    <div class="form-group">
                        <label>📦 Quantity (Required)</label>
                        <input type="number" id="adminQuantity" placeholder="Enter Quantity" min="1">
                    </div>
                    <div class="form-group">
                        <label>📏 Size (Required)</label>
                        <input type="text" id="adminSize" placeholder="Enter Size (e.g., 150mm x 120mm)">
                    </div>
                </div>
                <form id="emailForm">
                    <div class="form-group">
                        <label>📬 Recipient Email Address *</label>
                        <input type="email" id="recipientEmail" placeholder="client@example.com" required>
                    </div>
                    <button type="submit" class="btn" id="sendBtn">🚀 Send Form Link</button>
                </form>
            </div>

            <!-- GENERATE LINK TAB -->
            <div id="linkTab" class="tab-content">
                <div id="linkMessage" class="message"></div>
                <div class="po-config-box">
                    <h3>📦 PO Configuration</h3>
                    <div class="form-group">
                        <label>📋 PO Number</label>
                        <input type="text" id="poNumberLink" placeholder="Enter PO Number (e.g., PO-2026-001)">
                    </div>
                    <div class="form-group">
                        <label>📦 Quantity (Required)</label>
                        <input type="number" id="adminQuantityLink" placeholder="Enter Quantity" min="1">
                    </div>
                    <div class="form-group">
                        <label>📏 Size (Required)</label>
                        <input type="text" id="adminSizeLink" placeholder="Enter Size (e.g., 150mm x 120mm)">
                    </div>
                </div>
                <form id="linkForm">
                    <button type="submit" class="btn link-btn" id="generateBtn">🔗 Generate Form Link</button>
                </form>
                <div id="generatedLink" class="generated-link">
                    <strong>✅ Generated Link:</strong>
                    <p id="linkUrl" style="margin-top: 10px; font-family: monospace; font-size: 14px;"></p>
                    <button class="copy-btn" onclick="copyLink()">📋 Copy Link</button>
                </div>
            </div>

            <!-- SIZE MANAGEMENT TAB -->
            <div id="sizesTab" class="tab-content">
                <div id="sizeMessage" class="message"></div>
                <div style="background:#fff9e6;padding:15px;border-radius:8px;margin-bottom:20px;border-left:5px solid #ffc107;">
                    <strong>📏 Size Management</strong>
                    <p style="margin-top:8px;font-size:14px;">Add custom sizes for each bag type. These sizes will appear as dropdown options when clients fill the form.</p>
                </div>
                <form id="sizeForm">
                    <div class="form-group">
                        <label>Select Bag Type *</label>
                        <select id="bagTypeSelect" required>
                            <option value="">-- Select Bag Type --</option>
                            <option value="collar">⭕ Collar Type</option>
                            <option value="snap">📌 Snap Type</option>
                            <option value="ring">Ring Type</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Size Name *</label>
                        <input type="text" id="sizeName" placeholder="e.g., 150mm x 120mm" required>
                    </div>
                    <button type="submit" class="btn" id="addSizeBtn">➕ Add Size</button>
                </form>
                <div style="margin-top:30px;">
                    <h3 style="color:#667eea;margin-bottom:15px;">📋 Existing Sizes</h3>
                    <div class="form-group">
                        <label>Filter by Bag Type</label>
                        <select id="filterBagType" onchange="loadSizes()">
                            <option value="collar">⭕ Collar Type</option>
                            <option value="snap">📌 Snap Type</option>
                            <option value="ring">Ring Type</option>
                        </select>
                    </div>
                    <div id="sizesList" style="margin-top:15px;max-height:400px;overflow-y:auto;"></div>
                </div>
            </div>

            <center>
                <a href="/submissions" class="view-link">📊 View All Submissions</a>
            </center>
        </div>

        <div class="footer"><strong>Filter Bag Specification System</strong></div>
    </div>

    <script>
        function switchTab(tab, event) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            if (tab === 'email') document.getElementById('emailTab').classList.add('active');
            else if (tab === 'link') document.getElementById('linkTab').classList.add('active');
            else if (tab === 'sizes') { document.getElementById('sizesTab').classList.add('active'); loadSizes(); }
        }

        document.getElementById('emailForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('sendBtn');
            const msg = document.getElementById('emailMessage');
            btn.disabled = true; btn.textContent = 'Sending email...'; msg.style.display = 'none';
            try {
                const r = await fetch('/api/send-form', { method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({
                        recipient_email: document.getElementById('recipientEmail').value,
                        po_number: document.getElementById('poNumber').value,
                        admin_quantity: document.getElementById('adminQuantity').value,
                        admin_size: document.getElementById('adminSize').value
                    })});
                const d = await r.json();
                msg.style.display = 'block';
                msg.className = 'message ' + (d.success ? 'success' : 'error');
                msg.innerHTML = (d.success ? '✅ ' : '❌ ') + d.message;
                if (d.success) { document.getElementById('emailForm').reset(); document.getElementById('poNumber').value=''; document.getElementById('adminQuantity').value=''; document.getElementById('adminSize').value=''; }
            } catch(err) { msg.style.display='block'; msg.className='message error'; msg.innerHTML='❌ '+err.message; }
            finally { btn.disabled=false; btn.textContent='🚀 Send Form Link'; }
        });

        document.getElementById('linkForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('generateBtn');
            const msg = document.getElementById('linkMessage');
            const linkDiv = document.getElementById('generatedLink');
            btn.disabled=true; btn.textContent='Generating link...'; msg.style.display='none'; linkDiv.style.display='none';
            try {
                const r = await fetch('/api/generate-link', { method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({
                        po_number: document.getElementById('poNumberLink').value,
                        admin_quantity: document.getElementById('adminQuantityLink').value,
                        admin_size: document.getElementById('adminSizeLink').value
                    })});
                const d = await r.json();
                msg.style.display='block'; msg.className='message '+(d.success?'success':'error'); msg.innerHTML=(d.success?'✅ ':'❌ ')+d.message;
                if (d.success) { document.getElementById('linkUrl').textContent=d.form_url; linkDiv.style.display='block'; }
            } catch(err) { msg.style.display='block'; msg.className='message error'; msg.innerHTML='❌ '+err.message; }
            finally { btn.disabled=false; btn.textContent='🔗 Generate Form Link'; }
        });

        function copyLink() { navigator.clipboard.writeText(document.getElementById('linkUrl').textContent).then(()=>{alert('✅ Link copied to clipboard!');}); }

        document.getElementById('sizeForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('addSizeBtn');
            const msg = document.getElementById('sizeMessage');
            const bagType = document.getElementById('bagTypeSelect').value;
            const sizeName = document.getElementById('sizeName').value;
            if (!bagType || !sizeName) { msg.style.display='block'; msg.className='message error'; msg.innerHTML='❌ Please fill all fields'; return; }
            btn.disabled=true; btn.textContent='Adding...'; msg.style.display='none';
            try {
                const r = await fetch('/api/sizes', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({bag_type:bagType,size_name:sizeName})});
                const d = await r.json();
                msg.style.display='block'; msg.className='message '+(d.success?'success':'error'); msg.innerHTML=(d.success?'✅ ':'❌ ')+d.message;
                if (d.success) { document.getElementById('sizeForm').reset(); if(document.getElementById('filterBagType').value===bagType) loadSizes(); }
            } catch(err) { msg.style.display='block'; msg.className='message error'; msg.innerHTML='❌ '+err.message; }
            finally { btn.disabled=false; btn.textContent='➕ Add Size'; }
        });

        async function loadSizes() {
            const bagType = document.getElementById('filterBagType').value;
            const list = document.getElementById('sizesList');
            list.innerHTML='<p style="text-align:center;color:#999;">Loading...</p>';
            try {
                const r = await fetch(`/api/sizes/${bagType}`);
                const d = await r.json();
                if (d.success && d.sizes.length > 0) {
                    list.innerHTML = d.sizes.map(s => `
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 15px;background:#f8f9ff;border-radius:8px;margin-bottom:10px;border:1px solid #ddd;">
                            <span style="font-weight:500;color:#333;">${s.size_name}</span>
                            <button onclick="deleteSize(${s.id},'${s.size_name}')" style="background:#dc3545;color:white;border:none;padding:6px 15px;border-radius:5px;cursor:pointer;font-size:14px;">🗑️ Delete</button>
                        </div>`).join('');
                } else { list.innerHTML='<p style="text-align:center;color:#999;padding:30px;">No sizes added yet for this bag type.</p>'; }
            } catch(err) { list.innerHTML=`<p style="text-align:center;color:#dc3545;">Error: ${err.message}</p>`; }
        }

        async function deleteSize(sizeId, sizeName) {
            if (!confirm(`Delete size "${sizeName}"?`)) return;
            const r = await fetch(`/api/sizes/${sizeId}`, {method:'DELETE'});
            const d = await r.json();
            if (d.success) {
                loadSizes();
                const msg = document.getElementById('sizeMessage');
                msg.style.display='block'; msg.className='message success'; msg.innerHTML=`✅ Size "${sizeName}" deleted successfully`;
                setTimeout(()=>{msg.style.display='none';},3000);
            } else { alert(`Error: ${d.message}`); }
        }
    </script>
</body>
</html>
"""

FILTER_FORM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Filter Bag Specification Form</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #1f3c88 0%, #1e5aa8 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; }
        .header { background: linear-gradient(135deg, #1f3c88 0%, #1e5aa8 100%); padding: 25px 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .brand-wrapper { display: flex; align-items: center; justify-content: center; gap: 20px; }
        .brand-logo { height: 150px; width: auto; object-fit: contain; }
        .brand-text { text-align: left; }
        .brand-text h1 { font-size: 26px; margin: 0; color: white; font-weight: 700; line-height: 1.2; }
        .brand-text p { font-size: 15px; color: #ffd54f; font-weight: 500; margin-top: 5px; }
        .content { padding: 40px; }
        .po-info { background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 25px; border-left: 5px solid #ffc107; }
        .po-info strong { color: #856404; }
        .info-box { background: #e3f2fd; padding: 20px; border-radius: 10px; margin-bottom: 30px; border-left: 5px solid #1e5aa8; }
        .bag-specifications-container { display: flex; flex-direction: column; gap: 30px; }
        .bag-spec-card { border: 3px solid #1e5aa8; border-radius: 15px; padding: 30px; background: #f8f9ff; position: relative; animation: slideIn 0.3s ease; }
        @keyframes slideIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        .bag-spec-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding-bottom: 15px; border-bottom: 2px solid #1e5aa8; }
        .bag-spec-number { font-size: 1.4em; font-weight: 700; color: #1f3c88; }
        .form-section { margin-bottom: 40px; }
        .section-title { font-size: 1.3em; color: #1f3c88; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #1e5aa8; }
        .bag-type-selection { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
        .bag-type-card { border: 3px solid #ddd; border-radius: 15px; padding: 15px; cursor: pointer; transition: all 0.3s; text-align: center; background: white; position: relative; }
        .bag-type-card:hover { border-color: #1e5aa8; box-shadow: 0 5px 15px rgba(30, 90, 168, 0.3); transform: translateY(-3px); }
        .bag-type-card.selected { border-color: #1e5aa8; background: #e3f2fd; box-shadow: 0 8px 20px rgba(30, 90, 168, 0.4); }
        .bag-type-card input[type="radio"] { display: none; }
        .bag-type-img { width: 100%; height: 120px; object-fit: contain; margin-bottom: 10px; }
        .bag-type-name { font-size: 1.1em; font-weight: 600; color: #1f3c88; margin-bottom: 8px; }
        .bag-type-desc { font-size: 0.85em; color: #666; }
        .ring-image-container { display: flex; gap: 8px; justify-content: center; align-items: center; }
        .ring-image-container img { width: 45%; height: 100px; object-fit: contain; }
        .conditional-section { display: none; padding: 20px; background: white; border-radius: 10px; border: 2px solid #e3f2fd; margin-top: 15px; }
        .conditional-section.active { display: block; animation: slideDown 0.3s ease; }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
        .form-group { margin-bottom: 18px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #1f3c88; font-size: 0.95em; }
        input, textarea { width: 100%; padding: 12px 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 15px; font-family: inherit; transition: all 0.3s; }
        input:focus, textarea:focus { outline: none; border-color: #1e5aa8; box-shadow: 0 0 0 3px rgba(30, 90, 168, 0.1); }
        textarea { min-height: 80px; resize: vertical; }
        .field-with-image { display: flex; gap: 15px; align-items: flex-start; }
        .field-wrapper { flex: 1; }
        .reference-image { width: 120px; height: 120px; object-fit: contain; border: 2px solid #ddd; border-radius: 8px; padding: 5px; background: white; }
        .submit-btn { width: 100%; max-width: 400px; display: block; margin: 30px auto 0; padding: 16px 30px; background: linear-gradient(135deg, #1f3c88 0%, #1e5aa8 100%); color: white; border: none; border-radius: 10px; font-size: 1.1em; font-weight: 600; cursor: pointer; transition: all 0.3s; }
        .submit-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(30, 90, 168, 0.4); }
        .submit-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .message { padding: 15px; border-radius: 8px; margin-bottom: 20px; display: none; font-weight: 500; }
        .success { background: #d4edda; color: #155724; border: 2px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 2px solid #f5c6cb; }
        .footer { text-align: center; padding: 25px; background: #f5f5f5; color: #666; font-size: 0.9em; }
        .loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; align-items: center; justify-content: center; }
        .loading-overlay.active { display: flex; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #1e5aa8; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @media (max-width: 768px) {
            .brand-wrapper { flex-direction: column; gap: 15px; }
            .brand-logo { height: 60px; }
            .brand-text { text-align: center; }
            .brand-text h1 { font-size: 20px; }
            .content { padding: 25px; }
            .bag-spec-card { padding: 20px; }
            .bag-type-selection { grid-template-columns: 1fr; }
            .submit-btn { max-width: 100%; }
            .field-with-image { flex-direction: column; }
            .reference-image { width: 100%; max-width: 200px; margin: 10px auto 0; }
        }
        @media (max-width: 480px) {
            body { padding: 10px; }
            .content { padding: 20px; }
            .bag-spec-card { padding: 15px; }
        }
    </style>
</head>
<body>
    <div class="loading-overlay" id="loadingOverlay">
        <div class="spinner"></div>
    </div>

    <div class="container">
        <div class="header">
            <div class="brand-wrapper">
                <img src="{{ url_for('static', filename='logo.png') }}" class="brand-logo" alt="Company Logo">
                <div class="brand-text">
                    <h1>Vaayushanti Solutions Pvt Ltd</h1>
                    <p>Filter Bag Specification Form</p>
                </div>
            </div>
        </div>

        <div class="content">
            <div id="message" class="message"></div>
            {% if po_number or admin_quantity or admin_size %}
            <div class="po-info">
                {% if po_number %}<div><strong>Your PO Number:</strong> {{ po_number }}</div>{% endif %}
                {% if admin_quantity %}<div><strong>Your Quantity:</strong> {{ admin_quantity }}</div>{% endif %}
                {% if admin_size %}<div><strong>Your Size:</strong> {{ admin_size }}</div>{% endif %}
            </div>
            {% endif %}

            <div class="info-box">
                <strong>Dear sir/mam,</strong><br>
                kindly fill the filter bag specifications necessary for production
            </div>

            <form id="specForm" novalidate>
                <div class="form-group">
                    <label>Your Name *</label>
                    <input type="text" id="clientNameInput" required>
                </div>

                <div class="bag-specifications-container" id="bagSpecsContainer"></div>

                <div class="form-section">
                    <div class="section-title">Additional Information (Optional)</div>
                    <div class="form-group">
                        <label>Overall Remarks</label>
                        <textarea id="globalRemarks" placeholder="Any special requirements or notes for all bags"></textarea>
                    </div>
                </div>

                <button type="submit" class="submit-btn" id="submitBtn">📩 Submit All Specifications</button>
            </form>
        </div>

        <div class="footer">
            <strong>Thank you for choosing our filter bags!</strong><br>
            For any queries, contact us at crm@vaayushanti.org
        </div>
    </div>

    <script>
        function createBagCard(bagNumber) {
            return `
                <div class="bag-spec-card" data-bag-id="${bagNumber}">
                    <div class="bag-spec-header">
                        <div class="bag-spec-number">🛍️ Bag Specification #${bagNumber}</div>
                    </div>
                    <div class="form-group">
                        <label>Select Bag Type *</label>
                        <div class="bag-type-selection">
                            <label class="bag-type-card" data-bag="${bagNumber}" data-type="collar">
                                <input type="radio" name="bag_type_${bagNumber}" value="collar">
                                <img src="{{ url_for('static', filename='collar.webp') }}" class="bag-type-img" alt="Collar">
                                <div class="bag-type-name">⭕ Collar</div>
                                <div class="bag-type-desc">Collar Type</div>
                            </label>
                            <label class="bag-type-card" data-bag="${bagNumber}" data-type="snap">
                                <input type="radio" name="bag_type_${bagNumber}" value="snap">
                                <img src="{{ url_for('static', filename='snap-ring.jpeg') }}" class="bag-type-img" alt="Snap">
                                <div class="bag-type-name">📌 Snap</div>
                                <div class="bag-type-desc">Snap Type</div>
                            </label>
                            <label class="bag-type-card" data-bag="${bagNumber}" data-type="ring">
                                <input type="radio" name="bag_type_${bagNumber}" value="ring">
                                <div class="ring-image-container">
                                    <img src="{{ url_for('static', filename='GI.jpeg') }}" alt="Steel Ring">
                                </div>
                                <div class="bag-type-name">Ring</div>
                                <div class="bag-type-desc">Ring Type</div>
                            </label>
                        </div>
                    </div>
                    <div id="collarFields_${bagNumber}" class="conditional-section">
                        <h3 style="margin-bottom:15px;color:#1f3c88;">⭕ Collar Type Specifications</h3>
                        <div class="form-group">
                            <label>Collar OD (Outer Diameter) *</label>
                            <input type="text" id="collarOD_${bagNumber}" list="collarSizes_${bagNumber}" placeholder="Enter or select size (e.g. 150mm)">
                            <datalist id="collarSizes_${bagNumber}"></datalist>
                        </div>
                        <div class="form-group">
                            <label>Collar ID (Inner Diameter) *</label>
                            <input type="text" id="collarID_${bagNumber}" list="collarSizes_${bagNumber}" placeholder="Enter or select size (e.g. 140mm)">
                        </div>
                    </div>
                    <div id="snapFields_${bagNumber}" class="conditional-section">
                        <h3 style="margin-bottom:15px;color:#1f3c88;">📌 Snap Type Specifications</h3>
                        <div class="form-group">
                            <label>Tubesheet Data *</label>
                            <div class="field-with-image">
                                <div class="field-wrapper">
                                    <input type="text" id="tubesheetData_${bagNumber}" list="snapSizes_${bagNumber}" placeholder="Enter or select size">
                                    <datalist id="snapSizes_${bagNumber}"></datalist>
                                </div>
                                <img src="{{ url_for('static', filename='tubesheet.jpeg') }}" class="reference-image" alt="Tubesheet Reference">
                            </div>
                        </div>
                    </div>
                    <div id="ringFields_${bagNumber}" class="conditional-section">
                        <h3 style="margin-bottom:15px;color:#1f3c88;">Ring Type Specifications</h3>
                        <div class="form-group">
                            <label>Tubesheet Diameter *</label>
                            <div class="field-with-image">
                                <div class="field-wrapper">
                                    <input type="text" id="tubesheetDia_${bagNumber}" list="ringSizes_${bagNumber}" placeholder="Enter or select diameter">
                                    <datalist id="ringSizes_${bagNumber}"></datalist>
                                </div>
                                <img src="{{ url_for('static', filename='tubesheet.jpeg') }}" class="reference-image" alt="Tubesheet Reference">
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        function attachBagTypeListeners(bagNumber) {
            const cards = document.querySelectorAll(`[data-bag="${bagNumber}"]`);
            cards.forEach(card => {
                card.addEventListener('click', function() {
                    cards.forEach(c => c.classList.remove('selected'));
                    this.classList.add('selected');
                    const radio = this.querySelector('input[type="radio"]');
                    radio.checked = true;
                    ['collar','snap','ring'].forEach(t => document.getElementById(`${t}Fields_${bagNumber}`).classList.remove('active'));
                    document.getElementById(`${radio.value}Fields_${bagNumber}`).classList.add('active');
                    loadBagSizes(bagNumber, radio.value);
                });
            });
        }

        async function loadBagSizes(bagNumber, bagType) {
            try {
                const r = await fetch(`/api/sizes/${bagType}`);
                const d = await r.json();
                if (!d.success) return;
                const dlId = bagType === 'collar' ? `collarSizes_${bagNumber}` : bagType === 'snap' ? `snapSizes_${bagNumber}` : `ringSizes_${bagNumber}`;
                const dl = document.getElementById(dlId);
                if (dl) dl.innerHTML = d.sizes.map(s => `<option value="${s.size_name}"></option>`).join('');
            } catch(e) { console.error('Error loading sizes:', e); }
        }

        document.getElementById('specForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            const messageDiv = document.getElementById('message');
            const loadingOverlay = document.getElementById('loadingOverlay');
            const bags = [];
            const bagCards = document.querySelectorAll('.bag-spec-card');
            const clientName = document.getElementById('clientNameInput').value.trim();
            if (!clientName) { showMessage("Please enter your Name", "error"); return; }

            for (let card of bagCards) {
                const bagId = card.getAttribute('data-bag-id');
                const selectedRadio = document.querySelector(`input[name="bag_type_${bagId}"]:checked`);
                if (!selectedRadio) { showMessage(`Please select a bag type for Bag #${bagId}`, 'error'); return; }
                const bagType = selectedRadio.value;
                let bagData = { bag_type: bagType, client_name: clientName };
                if (bagType === 'collar') {
                    const od = document.getElementById(`collarOD_${bagId}`).value.trim();
                    const id = document.getElementById(`collarID_${bagId}`).value.trim();
                    if (!od || !id) { showMessage(`Please fill Collar OD and ID for Bag #${bagId}`, 'error'); return; }
                    bagData.collar_od = od; bagData.collar_id = id;
                } else if (bagType === 'snap') {
                    const ts = document.getElementById(`tubesheetData_${bagId}`).value.trim();
                    if (!ts) { showMessage(`Please provide Tubesheet Data for Bag #${bagId}`, 'error'); return; }
                    bagData.tubesheet_data = ts;
                } else if (bagType === 'ring') {
                    const dia = document.getElementById(`tubesheetDia_${bagId}`).value.trim();
                    if (!dia) { showMessage(`Please provide Tubesheet Diameter for Bag #${bagId}`, 'error'); return; }
                    bagData.tubesheet_dia = dia;
                }
                bags.push(bagData);
            }

            btn.disabled = true; btn.textContent = '⏳ Submitting...';
            loadingOverlay.classList.add('active'); messageDiv.style.display = 'none';

            try {
                const r = await fetch('/api/submit-form/{{ token }}', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({bags, global_remarks: document.getElementById('globalRemarks').value || null})
                });
                const d = await r.json();
                loadingOverlay.classList.remove('active');
                if (d.success) {
                    document.querySelector('.content').innerHTML = `
                        <div style="text-align:center;padding:60px 20px;">
                            <div style="font-size:4rem;margin-bottom:20px;">✅</div>
                            <h2 style="color:#28a745;margin-bottom:10px;">Thank You!</h2>
                            <p style="color:#555;font-size:1.1em;">Your filter bag specification has been submitted successfully.</p>
                        </div>`;
                } else {
                    showMessage('❌ ' + d.message, 'error');
                    btn.disabled = false; btn.textContent = '📩 Submit All Specifications';
                }
            } catch(err) {
                loadingOverlay.classList.remove('active');
                showMessage('❌ Error: ' + err.message, 'error');
                btn.disabled = false; btn.textContent = '📩 Submit All Specifications';
            }
        });

        function showMessage(text, type) {
            const md = document.getElementById('message');
            md.style.display = 'block'; md.className = `message ${type}`; md.innerHTML = text;
            md.scrollIntoView({behavior:'smooth', block:'nearest'});
        }

        document.addEventListener('DOMContentLoaded', function() {
            const container = document.getElementById('bagSpecsContainer');
            container.innerHTML = createBagCard(1);
            attachBagTypeListeners(1);
        });
    </script>
</body>
</html>
"""

SUBMISSIONS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Submissions</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 15px 15px 0 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; }
        .header h1 { color: #667eea; margin-bottom: 6px; }
        .nav-links { display: flex; gap: 10px; }
        .back-link { display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; font-size: 14px; }
        .back-link:hover { background: #764ba2; }
        .logout-link { display: inline-block; padding: 10px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 8px; font-size: 14px; }
        .logout-link:hover { background: #c82333; }
        .submissions { background: white; padding: 30px; border-radius: 0 0 15px 15px; }
        .submission-card { background: #f8f9ff; padding: 25px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #667eea; }
        .submission-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 15px; border-bottom: 2px solid #ddd; }
        .badge { padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: 600; }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-pending { background: #fff3cd; color: #856404; }
        .badge-superseded { background: #e2d9f3; color: #4a235a; }
        .detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; margin-top: 10px; }
        .detail-item { background: white; border-radius: 8px; padding: 12px 15px; border: 1px solid #e0e0e0; }
        .detail-label { font-size: 12px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
        .detail-value { font-size: 15px; color: #333; font-weight: 500; }
        .empty-state { text-align: center; padding: 60px 20px; color: #666; }
        .po-badge { background: #ffc107; color: #000; padding: 5px 12px; border-radius: 5px; font-weight: 600; font-size: 14px; margin-left: 10px; }
        .qty-badge { background: #17a2b8; color: white; padding: 5px 12px; border-radius: 5px; font-weight: 600; font-size: 14px; margin-left: 6px; }
        .size-badge { background: #6f42c1; color: white; padding: 5px 12px; border-radius: 5px; font-weight: 600; font-size: 14px; margin-left: 6px; }
        .section-divider { margin: 15px 0; border: none; border-top: 1px dashed #ddd; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>📊 All Submissions</h1>
                <p style="color:#666;">View all filter bag specification submissions</p>
            </div>
            <div class="nav-links">
                <a href="/" class="back-link">← Back to Sender</a>
                <a href="/admin/logout" class="logout-link">🚪 Logout</a>
            </div>
        </div>
        <div class="submissions">
            {% if submissions %}
                {% for submission in submissions %}
                <div class="submission-card">
                    <div class="submission-header">
                        <div>
                            <h3>
                                {% if submission.submitted %}{{ submission.client_name or 'N/A' }}
                                {% else %}Pending Submission{% endif %}
                                {% if submission.po_number %}<span class="po-badge">PO: {{ submission.po_number }}</span>{% endif %}
                                {% if submission.admin_quantity %}<span class="qty-badge">Qty: {{ submission.admin_quantity }}</span>{% endif %}
                                {% if submission.admin_size %}<span class="size-badge">📏 {{ submission.admin_size }}</span>{% endif %}
                            </h3>
                            <p style="color:#666;font-size:14px;margin-top:5px;">Created: {{ submission.created_at.strftime('%d %b %Y, %I:%M %p') }}</p>
                        </div>
                        <span class="badge {% if submission.superseded %}badge-superseded{% elif submission.submitted %}badge-success{% else %}badge-pending{% endif %}">
                            {% if submission.superseded %}🔄 Re-Submitted{% elif submission.submitted %}✓ Submitted{% else %}⏳ Pending{% endif %}
                        </span>
                    </div>
                    <div class="detail-grid">
                        {% if submission.superseded %}
                        <div style="grid-column:1/-1;background:#f3e8ff;padding:10px 15px;border-radius:8px;border-left:4px solid #7c3aed;font-size:13px;color:#4a235a;">
                            🔄 <strong>Purana Submission</strong> — Client ne baad mein re-submit kiya hai. Yeh record history ke liye preserve hai.
                        </div>
                        {% endif %}
                        <div class="detail-item">
                            <div class="detail-label">📬 Recipient Email</div>
                            <div class="detail-value">{{ submission.recipient_email }}</div>
                        </div>
                        {% if submission.po_number %}
                        <div class="detail-item">
                            <div class="detail-label">📋 PO Number</div>
                            <div class="detail-value">{{ submission.po_number }}</div>
                        </div>
                        {% endif %}
                        {% if submission.admin_quantity %}
                        <div class="detail-item">
                            <div class="detail-label">📦 Quantity</div>
                            <div class="detail-value">{{ submission.admin_quantity }}</div>
                        </div>
                        {% endif %}
                        {% if submission.admin_size %}
                        <div class="detail-item">
                            <div class="detail-label">📏 Size</div>
                            <div class="detail-value">{{ submission.admin_size }}</div>
                        </div>
                        {% endif %}
                    </div>
                    {% if submission.submitted and submission.bag_type %}
                        <hr class="section-divider">
                        <p style="font-size:13px;color:#888;margin-bottom:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Client Submission Details</p>
                        <div class="detail-grid">
                            <div class="detail-item"><div class="detail-label">👤 Client Name</div><div class="detail-value">{{ submission.client_name or 'N/A' }}</div></div>
                            <div class="detail-item"><div class="detail-label">🛍️ Bag Type</div><div class="detail-value">{{ submission.bag_type.title() if submission.bag_type else 'N/A' }}</div></div>
                            {% if submission.bag_type == 'collar' %}
                            <div class="detail-item"><div class="detail-label">⭕ Collar OD</div><div class="detail-value">{{ submission.collar_od or 'N/A' }}</div></div>
                            <div class="detail-item"><div class="detail-label">⭕ Collar ID</div><div class="detail-value">{{ submission.collar_id or 'N/A' }}</div></div>
                            {% elif submission.bag_type == 'snap' %}
                            <div class="detail-item"><div class="detail-label">📌 Tubesheet Data</div><div class="detail-value">{{ submission.tubesheet_data or 'N/A' }}</div></div>
                            {% elif submission.bag_type == 'ring' %}
                            <div class="detail-item"><div class="detail-label">💍 Tubesheet Diameter</div><div class="detail-value">{{ submission.tubesheet_dia or 'N/A' }}</div></div>
                            {% endif %}
                            <div class="detail-item">
                                <div class="detail-label">🕐 Submitted At</div>
                                <div class="detail-value">{% if submission.submitted_at %}{{ submission.submitted_at.strftime('%d %b %Y, %I:%M %p') }}{% else %}N/A{% endif %}</div>
                            </div>
                        </div>
                        {% if submission.remarks %}
                        <div style="margin-top:12px;background:white;border-radius:8px;padding:12px 15px;border:1px solid #e0e0e0;">
                            <div class="detail-label">📝 Remarks</div>
                            <div class="detail-value" style="margin-top:4px;">{{ submission.remarks }}</div>
                        </div>
                        {% endif %}
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h2>📭 No Submissions Yet</h2>
                    <p>Send a form link to get started!</p>
                </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

# ==================== RUN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Filter Bag Specification System")
    print("   PostgreSQL + Admin Login Edition")
    print("=" * 60)
    print(f"📧 Sender Email : {SENDER_EMAIL}")
    print(f"👤 Admin User   : {ADMIN_USERNAME}")
    print(f"🗄️  Database     : PostgreSQL")
    print("=" * 60)
    print("\n📍 Routes:")
    print("   /admin/login  → Admin Login Page")
    print("   /             → Sender Dashboard (login required)")
    print("   /submissions  → All Submissions  (login required)")
    print("   /form/<token> → Client Form      (public)")
    print("=" * 60)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
