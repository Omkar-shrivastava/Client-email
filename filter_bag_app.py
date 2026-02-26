"""
Filter Bag Specification System - Complete Flask Application with PO Feature + Multiple Bags
Author: Claude
Features: Email sender, Form receiver, Database storage with SQLAlchemy, PO Number Management, MULTIPLE BAGS SUPPORT
"""

from flask import Flask, render_template_string, request, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import secrets
import os
import socket
socket.setdefaulttimeout(10)



# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///filter_bags.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Database
db = SQLAlchemy(app)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

# ==================== DATABASE MODELS ====================

class FilterBagSubmission(db.Model):
    __tablename__ = 'filter_bag_submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), nullable=False, index=True)
    recipient_email = db.Column(db.String(200), nullable=False)
    po_number = db.Column(db.String(100))
    
    # Bag Type
    bag_type = db.Column(db.String(50))
    
    # Collar Type Fields
    collar_od = db.Column(db.String(100))
    collar_id = db.Column(db.String(100))
    
    # Snap Type Fields
    tubesheet_data = db.Column(db.Text)
    
    # Ring Type Fields
    tubesheet_dia = db.Column(db.String(100))
    
    # Client Information
    client_name = db.Column(db.String(200))
    client_email = db.Column(db.String(200))
    quantity = db.Column(db.Integer)
    delivery_date = db.Column(db.String(50))
    remarks = db.Column(db.Text)
    
    # Metadata
    submitted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    
    #new admin section 
    admin_quantity = db.Column(db.Integer)
    admin_size = db.Column(db.String(200))

    def __repr__(self):
        return f'<Submission {self.id} - {self.recipient_email}>'


class BagSize(db.Model):
    __tablename__ = 'bag_sizes'
    
    id = db.Column(db.Integer, primary_key=True)
    size_name = db.Column(db.String(100), nullable=False)
    bag_type = db.Column(db.String(50), nullable=False)  # collar, snap, ring
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BagSize {self.size_name} - {self.bag_type}>'

# Create tables
with app.app_context():
    db.create_all()


# ==================== HELPER: Get Parent Submission ====================

def get_parent_submission(token):
    """
    FIX: Reliably fetch the original (parent) record for a token.
    Parent record = the one created by admin (has no bag_type).
    Falls back to the earliest record if needed.
    Works for both first-time submission AND edit/re-submit flow.
    Does NOT filter by submitted=False — that was the root cause of the bug.
    """
    # Primary: find the record with no bag_type — that's the admin-created parent
    parent = FilterBagSubmission.query.filter_by(
        token=token,
        bag_type=None
    ).order_by(FilterBagSubmission.id.asc()).first()

    if parent:
        return parent

    # Fallback: return the earliest record with this token
    return FilterBagSubmission.query.filter_by(
        token=token
    ).order_by(FilterBagSubmission.id.asc()).first()


# ==================== EMAIL FUNCTIONS ====================

def send_email_resend(to_email, subject, html_body):
    """Send email using Resend API"""
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
    """Send form link to recipient via email (RESEND VERSION)"""
    try:
        form_url = url_for('filter_form', token=token, _external=True)

        po_info = f"<p><strong>PO Number:</strong> {po_number}</p>" if po_number else ""

        subject = "🔧 Filter Bag Specification Request"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 15px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔧 Filter Bag Specification Request</h1>
                    <p>We need your filter bag specifications</p>
                </div>
                <div class="content">
                    <p>Dear Valued Client,</p>
                    <p>To proceed with your order, we kindly request you to share the filter bag specifications.</p>
                    
                    {po_info}

                    <center>
                        <a href="{form_url}" class="button">📋 Fill Specification Form</a>
                    </center>

                    <p><strong>Note:</strong> This link is unique to you. You can use it to fill or edit your specifications.</p>
                </div>
                <div class="footer">
                    <p><strong>Filter Bag Specification System</strong></p>
                    <p>Contact: {SENDER_EMAIL}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return send_email_resend(recipient_email, subject, html_body)

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


def send_submission_notification(submissions_list):
    """Send notification to sender when form is submitted - UPDATED for multiple bags (RESEND)"""
    try:
        first_submission = submissions_list[0]
        bag_count = len(submissions_list)
        
        subject = f"✅ Form Submitted - {first_submission.client_name or 'Client'} ({bag_count} bag{'s' if bag_count > 1 else ''})"
        
        bags_details = ""
        for idx, submission in enumerate(submissions_list, 1):
            spec_details = ""
            if submission.bag_type == 'collar':
                spec_details = f"""
                <tr><td><strong>Collar OD:</strong></td><td>{submission.collar_od}</td></tr>
                <tr><td><strong>Collar ID:</strong></td><td>{submission.collar_id}</td></tr>
                """
            elif submission.bag_type == 'snap':
                spec_details = f"""
                <tr><td><strong>Tubesheet Data:</strong></td><td>{submission.tubesheet_data}</td></tr>
                """
            elif submission.bag_type == 'ring':
                spec_details = f"""
                <tr><td><strong>Tubesheet Diameter:</strong></td><td>{submission.tubesheet_dia}</td></tr>
                """
            
            bags_details += f"""
            <h4 style="color: #1f3c88; margin-top: 20px;">🛍️ Bag #{idx} - {submission.bag_type.title() if submission.bag_type else 'N/A'}</h4>
            <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Bag Type:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{submission.bag_type.title() if submission.bag_type else 'N/A'}</td>
                </tr>
                {spec_details}
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Quantity:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{submission.quantity or 'N/A'}</td>
                </tr>
            </table>
            """
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                .success-badge {{ background: #38ef7d; color: white; padding: 5px 15px; border-radius: 20px; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Form Submitted Successfully</h1>
                    <p class="success-badge">New Submission Received ({bag_count} Bag{'s' if bag_count > 1 else ''})</p>
                </div>
                <div class="content">
                    <p><strong>Good news!</strong> A client has successfully submitted the filter bag specification form.</p>
                    <h3>📋 Client Details:</h3>
                    <table>
                        <tr><td><strong>Client Name:</strong></td><td>{first_submission.client_name}</td></tr>
                        <tr><td><strong>Client Email:</strong></td><td>{first_submission.client_email}</td></tr>
                        <tr><td><strong>PO Number:</strong></td><td>{first_submission.po_number or 'N/A'}</td></tr>
                        <tr><td><strong>Quantity:</strong></td><td>{first_submission.admin_quantity or 'N/A'}</td></tr>
                        <tr><td><strong>Size:</strong></td><td>{first_submission.admin_size or 'N/A'}</td></tr>
                        <tr><td><strong>Total Bags:</strong></td><td>{bag_count}</td></tr>
                        <tr><td><strong>Submitted At:</strong></td><td>{first_submission.submitted_at.strftime('%d %b %Y, %I:%M %p') if first_submission.submitted_at else 'N/A'}</td></tr>
                    </table>
                    <h3 style="margin-top: 30px;">🛍️ Bag Specifications:</h3>
                    {bags_details}
                    <p style="margin-top: 20px;"><strong>Overall Remarks:</strong><br>{first_submission.remarks or 'No additional remarks'}</p>
                    <p>You can view all submissions in your dashboard.</p>
                </div>
                <div class="footer">
                    <p><strong>Filter Bag Specification System</strong></p>
                    <p>Automated notification - Do not reply to this email</p>
                </div>
            </div>
        </body>
        </html>
        """

        return send_email_resend(SENDER_EMAIL, subject, html_body)

    except Exception as e:
        print(f"❌ Error sending notification: {str(e)}")
        return False


def send_client_submission_notification(submissions_list):
    """Send detailed submission email to client with Edit option (RESEND)"""
    try:
        first_submission = submissions_list[0]
        bag_count = len(submissions_list)
        form_url = url_for('filter_form', token=first_submission.token, _external=True)
        subject = f"✅ Your Filter Bag Submission Details ({bag_count} Bag{'s' if bag_count > 1 else ''})"

        bags_details = ""
        for idx, submission in enumerate(submissions_list, 1):
            spec_details = ""
            if submission.bag_type == 'collar':
                spec_details = f"""
                <tr><td><strong>Collar OD:</strong></td><td>{submission.collar_od}</td></tr>
                <tr><td><strong>Collar ID:</strong></td><td>{submission.collar_id}</td></tr>
                """
            elif submission.bag_type == 'snap':
                spec_details = f"""
                <tr><td><strong>Tubesheet Data:</strong></td><td>{submission.tubesheet_data}</td></tr>
                """
            elif submission.bag_type == 'ring':
                spec_details = f"""
                <tr><td><strong>Tubesheet Diameter:</strong></td><td>{submission.tubesheet_dia}</td></tr>
                """

            bags_details += f"""
            <h4 style="color: #1f3c88; margin-top: 20px;">🛍️ Bag #{idx} - {submission.bag_type.title()}</h4>
            <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                <tr><td><strong>Bag Type:</strong></td><td>{submission.bag_type.title()}</td></tr>
                {spec_details}
                <tr><td><strong>Quantity:</strong></td><td>{submission.quantity}</td></tr>
            </table>
            """

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #1e5aa8; color: white; padding: 25px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                .edit-btn {{ display:inline-block; padding:12px 25px; background:#1e5aa8; color:white; text-decoration:none; border-radius:5px; margin-top:20px; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h2>✅ Thank You for Your Submission</h2></div>
                <div class="content">
                    <p>Your filter bag specification has been successfully submitted.</p>
                    <table>
                        <tr><td><strong>PO Number:</strong></td><td>{first_submission.po_number or 'N/A'}</td></tr>
                        <tr><td><strong>Quantity:</strong></td><td>{first_submission.admin_quantity or 'N/A'}</td></tr>
                        <tr><td><strong>Size:</strong></td><td>{first_submission.admin_size or 'N/A'}</td></tr>
                        <tr><td><strong>Total Bags Submitted:</strong></td><td>{bag_count}</td></tr>
                    </table>
                    <h3>📋 Submission Details</h3>
                    {bags_details}
                    <p><strong>Overall Remarks:</strong><br>{first_submission.remarks or 'No additional remarks'}</p>
                    <a href="{form_url}" class="edit-btn">✏️ Edit &amp; Re-Submit Form</a>
                    <p style="margin-top:20px;">If any information is incorrect, you can click the button above to update your submission.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return send_email_resend(first_submission.recipient_email, subject, html_body)

    except Exception as e:
        print(f"❌ Error sending client notification: {str(e)}")
        return False


# ==================== ROUTES ====================

@app.route('/')
@app.route('/sender')
def sender_page():
    """Admin page to send form links to recipients"""
    return render_template_string(SENDER_HTML)


@app.route('/api/send-form', methods=['POST'])
def send_form():
    """API endpoint to send form link to recipient"""
    try:
        data = request.get_json(silent=True) or {}

        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data'}), 400

        recipient_email = data.get('recipient_email', '').strip()
        po_number = data.get('po_number', '').strip()
        admin_quantity = data.get('admin_quantity')
        admin_size = data.get('admin_size', '').strip()

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
            return jsonify({'success': False, 'message': 'Failed to send email. Please check SMTP settings.'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/generate-link', methods=['POST'])
def generate_link():
    """API endpoint to generate form link without sending email"""
    try:
        data = request.get_json(silent=True) or {}
        po_number = data.get('po_number', '').strip()
        admin_quantity = data.get('admin_quantity')
        admin_size = data.get('admin_size', '').strip()

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
    """Display filter bag specification form to recipient"""

    # ✅ FIX: Use get_parent_submission() — removes submitted=False filter
    # This allows the form to open even after first submission (Edit & Re-Submit)
    submission = get_parent_submission(token)

    if not submission:
        return """
        <div style='text-align:center; padding:50px; font-family:Arial;'>
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
        # ✅ FIX: Use get_parent_submission() — removes submitted=False filter
        # This allows re-submission (Edit & Re-Submit) to work correctly
        parent_submission = get_parent_submission(token)

        if not parent_submission:
            return jsonify({
                'success': False,
                'message': 'Invalid form link. Please request a new link from the sender.'
            }), 404

        data = request.get_json(silent=True) or {}
        bags = data.get('bags', [])

        if not bags:
            return jsonify({'success': False, 'message': 'Please add bag specification'}), 400

        # ✅ FIX: On re-submission, delete previous child bag records for this token
        # Prevents duplicate entries accumulating in the database on edits
        FilterBagSubmission.query.filter(
            FilterBagSubmission.token == token,
            FilterBagSubmission.bag_type != None
        ).delete()
        db.session.flush()

        # ✅ SINGLE BAG ONLY
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

        # ✅ Always update parent — works for first submit AND re-submit
        parent_submission.submitted = True
        parent_submission.submitted_at = datetime.utcnow()

        db.session.commit()

        send_submission_notification([bag_submission])
        send_client_submission_notification([bag_submission])

        return jsonify({
            'success': True,
            'message': 'Successfully submitted bag specification! Thank you for your response.',
            'bags_count': 1
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error submitting form: {str(e)}'}), 500


@app.route('/submissions')
def view_submissions():
    """View all submissions (admin page)"""
    submissions = FilterBagSubmission.query.order_by(FilterBagSubmission.created_at.desc()).all()
    return render_template_string(SUBMISSIONS_HTML, submissions=submissions)


@app.route('/api/sizes', methods=['POST'])
def add_size():
    """Add a new bag size"""
    try:
        data = request.get_json(silent=True) or {}
        size_name = data.get('size_name', '').strip()
        bag_type = data.get('bag_type', '').strip()
        
        if not size_name or not bag_type:
            return jsonify({'success': False, 'message': 'Size name and bag type required'}), 400
        
        existing = BagSize.query.filter_by(size_name=size_name, bag_type=bag_type).first()
        if existing:
            return jsonify({'success': False, 'message': 'This size already exists'}), 400
        
        new_size = BagSize(size_name=size_name, bag_type=bag_type)
        db.session.add(new_size)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Size "{size_name}" added successfully',
            'size': {'id': new_size.id, 'size_name': new_size.size_name, 'bag_type': new_size.bag_type}
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/sizes/<bag_type>', methods=['GET'])
def get_sizes(bag_type):
    """Get all sizes for a specific bag type"""
    try:
        sizes = BagSize.query.filter_by(bag_type=bag_type).order_by(BagSize.created_at.desc()).all()
        return jsonify({
            'success': True,
            'sizes': [{'id': s.id, 'size_name': s.size_name} for s in sizes]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/sizes/<int:size_id>', methods=['DELETE'])
def delete_size(size_id):
    """Delete a bag size"""
    try:
        size = BagSize.query.get(size_id)
        if not size:
            return jsonify({'success': False, 'message': 'Size not found'}), 404
        
        db.session.delete(size)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Size deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ==================== HTML TEMPLATES ====================

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
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .content { padding: 40px; }
        .info-box { background: #e3f2fd; padding: 20px; border-radius: 10px; margin-bottom: 30px; border-left: 5px solid #2196F3; }
        .form-group { margin-bottom: 25px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #333; }
        input { width: 100%; padding: 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; transition: all 0.3s; }
        input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .btn { width: 100%; padding: 18px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
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
        select { cursor: pointer; }
        select:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .po-config-box { background:#fff3cd; padding:20px; border-radius:10px; margin-bottom:30px; border-left:5px solid #ffc107; }
        .po-config-box h3 { margin-bottom:15px; color:#856404; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
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

            <!-- ===== EMAIL TAB ===== -->
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

            <!-- ===== GENERATE LINK TAB ===== -->
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

            <!-- ===== SIZE MANAGEMENT TAB ===== -->
            <div id="sizesTab" class="tab-content">
                <div id="sizeMessage" class="message"></div>
                
                <div style="background: #fff9e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #ffc107;">
                    <strong>📏 Size Management</strong><br>
                    <p style="margin-top: 8px; font-size: 14px;">Add custom sizes for each bag type. These sizes will appear as dropdown options when clients fill the form.</p>
                </div>

                <form id="sizeForm">
                    <div class="form-group">
                        <label>Select Bag Type *</label>
                        <select id="bagTypeSelect" required style="width: 100%; padding: 15px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px;">
                            <option value="">-- Select Bag Type --</option>
                            <option value="collar">⭕ Collar Type</option>
                            <option value="snap">📌 Snap Type</option>
                            <option value="ring"> Ring Type</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Size Name *</label>
                        <input type="text" id="sizeName" placeholder="e.g., 150mm x 120mm, 6 inch, Custom Size 1" required>
                    </div>
                    <button type="submit" class="btn" id="addSizeBtn">➕ Add Size</button>
                </form>

                <div style="margin-top: 30px;">
                    <h3 style="color: #667eea; margin-bottom: 15px;">📋 Existing Sizes</h3>
                    <div class="form-group">
                        <label>Filter by Bag Type</label>
                        <select id="filterBagType" onchange="loadSizes()" style="width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 15px;">
                            <option value="collar">⭕ Collar Type</option>
                            <option value="snap">📌 Snap Type</option>
                            <option value="ring">Ring Type</option>
                        </select>
                    </div>
                    <div id="sizesList" style="margin-top: 15px; max-height: 400px; overflow-y: auto;"></div>
                </div>
            </div>
            
            <center>
                <a href="/submissions" class="view-link">📊 View All Submissions</a>
            </center>
        </div>
        
        <div class="footer">
            <strong>Filter Bag Specification System</strong><br>
        </div>
    </div>

    <script>
        let currentTab = 'email';

        function switchTab(tab, event) {
            currentTab = tab;
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
            const messageDiv = document.getElementById('emailMessage');
            const email = document.getElementById('recipientEmail').value;
            const poNumber = document.getElementById('poNumber').value;
            const adminQuantity = document.getElementById('adminQuantity').value;
            const adminSize = document.getElementById('adminSize').value;   
            btn.disabled = true;
            btn.textContent = 'Sending email...';
            messageDiv.style.display = 'none';
            try {
                const response = await fetch('/api/send-form', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ recipient_email: email, po_number: poNumber, admin_quantity: adminQuantity, admin_size: adminSize })
                });
                const data = await response.json();
                messageDiv.style.display = 'block';
                if (data.success) {
                    messageDiv.className = 'message success';
                    messageDiv.innerHTML = `✅ ${data.message}`;
                    document.getElementById('emailForm').reset();
                    document.getElementById('poNumber').value = '';
                    document.getElementById('adminQuantity').value = '';
                    document.getElementById('adminSize').value = '';
                } else {
                    messageDiv.className = 'message error';
                    messageDiv.innerHTML = `❌ ${data.message}`;
                }
            } catch (error) {
                messageDiv.style.display = 'block';
                messageDiv.className = 'message error';
                messageDiv.innerHTML = `❌ Error: ${error.message}`;
            } finally {
                btn.disabled = false;
                btn.textContent = '🚀 Send Form Link';
            }
        });

        document.getElementById('linkForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('generateBtn');
            const messageDiv = document.getElementById('linkMessage');
            const generatedLinkDiv = document.getElementById('generatedLink');
            const poNumber = document.getElementById('poNumberLink').value;
            const adminQuantity = document.getElementById('adminQuantityLink').value;
            const adminSize = document.getElementById('adminSizeLink').value;
            btn.disabled = true;
            btn.textContent = 'Generating link...';
            messageDiv.style.display = 'none';
            generatedLinkDiv.style.display = 'none';
            try {
                const response = await fetch('/api/generate-link', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ po_number: poNumber, admin_quantity: adminQuantity, admin_size: adminSize })
                });
                const data = await response.json();
                if (data.success) {
                    messageDiv.style.display = 'block';
                    messageDiv.className = 'message success';
                    messageDiv.innerHTML = `✅ ${data.message}`;
                    document.getElementById('linkUrl').textContent = data.form_url;
                    generatedLinkDiv.style.display = 'block';
                } else {
                    messageDiv.style.display = 'block';
                    messageDiv.className = 'message error';
                    messageDiv.innerHTML = `❌ ${data.message}`;
                }
            } catch (error) {
                messageDiv.style.display = 'block';
                messageDiv.className = 'message error';
                messageDiv.innerHTML = `❌ Error: ${error.message}`;
            } finally {
                btn.disabled = false;
                btn.textContent = '🔗 Generate Form Link';
            }
        });

        function copyLink() {
            const linkText = document.getElementById('linkUrl').textContent;
            navigator.clipboard.writeText(linkText).then(() => { alert('✅ Link copied to clipboard!'); });
        }

        document.getElementById('sizeForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('addSizeBtn');
            const messageDiv = document.getElementById('sizeMessage');
            const bagType = document.getElementById('bagTypeSelect').value;
            const sizeName = document.getElementById('sizeName').value;
            if (!bagType || !sizeName) {
                messageDiv.style.display = 'block';
                messageDiv.className = 'message error';
                messageDiv.innerHTML = '❌ Please fill all fields';
                return;
            }
            btn.disabled = true;
            btn.textContent = 'Adding...';
            messageDiv.style.display = 'none';
            try {
                const response = await fetch('/api/sizes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bag_type: bagType, size_name: sizeName })
                });
                const data = await response.json();
                messageDiv.style.display = 'block';
                if (data.success) {
                    messageDiv.className = 'message success';
                    messageDiv.innerHTML = `✅ ${data.message}`;
                    document.getElementById('sizeForm').reset();
                    if (document.getElementById('filterBagType').value === bagType) loadSizes();
                } else {
                    messageDiv.className = 'message error';
                    messageDiv.innerHTML = `❌ ${data.message}`;
                }
            } catch (error) {
                messageDiv.style.display = 'block';
                messageDiv.className = 'message error';
                messageDiv.innerHTML = `❌ Error: ${error.message}`;
            } finally {
                btn.disabled = false;
                btn.textContent = '➕ Add Size';
            }
        });

        async function loadSizes() {
            const bagType = document.getElementById('filterBagType').value;
            const sizesList = document.getElementById('sizesList');
            sizesList.innerHTML = '<p style="text-align: center; color: #999;">Loading...</p>';
            try {
                const response = await fetch(`/api/sizes/${bagType}`);
                const data = await response.json();
                if (data.success && data.sizes.length > 0) {
                    sizesList.innerHTML = data.sizes.map(size => `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; background: #f8f9ff; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd;">
                            <span style="font-weight: 500; color: #333;">${size.size_name}</span>
                            <button onclick="deleteSize(${size.id}, '${size.size_name}')" style="background: #dc3545; color: white; border: none; padding: 6px 15px; border-radius: 5px; cursor: pointer; font-size: 14px;">🗑️ Delete</button>
                        </div>
                    `).join('');
                } else {
                    sizesList.innerHTML = '<p style="text-align: center; color: #999; padding: 30px;">No sizes added yet for this bag type.</p>';
                }
            } catch (error) {
                sizesList.innerHTML = `<p style="text-align: center; color: #dc3545;">Error loading sizes: ${error.message}</p>`;
            }
        }

        async function deleteSize(sizeId, sizeName) {
            if (!confirm(`Delete size "${sizeName}"?`)) return;
            try {
                const response = await fetch(`/api/sizes/${sizeId}`, { method: 'DELETE' });
                const data = await response.json();
                if (data.success) {
                    loadSizes();
                    const messageDiv = document.getElementById('sizeMessage');
                    messageDiv.style.display = 'block';
                    messageDiv.className = 'message success';
                    messageDiv.innerHTML = `✅ Size "${sizeName}" deleted successfully`;
                    setTimeout(() => { messageDiv.style.display = 'none'; }, 3000);
                } else {
                    alert(`Error: ${data.message}`);
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
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
        .add-bag-btn { width: 100%; max-width: 400px; display: block; margin: 30px auto; padding: 14px 25px; background: #28a745; color: white; border: 2px dashed #28a745; border-radius: 10px; font-size: 1em; font-weight: 600; cursor: pointer; transition: all 0.3s; }
        .add-bag-btn:hover { background: #218838; border-color: #218838; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3); }
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
            .brand-text p { font-size: 13px; }
            .content { padding: 25px; }
            .bag-spec-card { padding: 20px; }
            .bag-type-selection { grid-template-columns: 1fr; }
            .submit-btn, .add-bag-btn { max-width: 100%; font-size: 1em; padding: 14px 25px; }
            .ring-image-container { flex-direction: column; }
            .ring-image-container img { width: 100%; max-width: 250px; }
            .field-with-image { flex-direction: column; }
            .reference-image { width: 100%; max-width: 200px; margin: 10px auto 0; }
        }
        @media (max-width: 480px) {
            body { padding: 10px; }
            .content { padding: 20px; }
            .bag-spec-card { padding: 15px; }
            .brand-text h1 { font-size: 18px; }
            .section-title { font-size: 1.1em; }
            .submit-btn, .add-bag-btn { font-size: 0.95em; padding: 12px 20px; }
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
                {% if po_number %}<div><strong> Your PO Number:</strong> {{ po_number }}</div>{% endif %}
                {% if admin_quantity %}<div><strong> Your Quantity:</strong> {{ admin_quantity }}</div>{% endif %}
                {% if admin_size %}<div><strong> Your Size:</strong> {{ admin_size }}</div>{% endif %}
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

                <button type="submit" class="submit-btn" id="submitBtn">
                    📩 Submit All Specifications
                </button>
            </form>
        </div>
        
        <div class="footer">
            <strong>Thank you for choosing our filter bags!</strong><br>
            For any queries, contact us at crm@vaayushanti.org
        </div>
    </div>

    <script>
        let bagCounter = 1;

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
                                <div class="bag-type-name"> Ring</div>
                                <div class="bag-type-desc">Ring Type</div>
                            </label>
                        </div>
                    </div>
                    <div id="collarFields_${bagNumber}" class="conditional-section">
                        <h3 style="margin-bottom: 15px; color: #1f3c88;">⭕ Collar Type Specifications</h3>
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
                        <h3 style="margin-bottom: 15px; color: #1f3c88;">📌 Snap Type Specifications</h3>
                        <div class="form-group">
                            <label>Tubesheet Data *</label>
                            <div class="field-with-image">
                                <div class="field-wrapper">
                                    <input type="text" id="tubesheetData_${bagNumber}" list="snapSizes_${bagNumber}" placeholder="Enter or select size" required>
                                    <datalist id="snapSizes_${bagNumber}"></datalist>
                                </div>
                                <img src="{{ url_for('static', filename='tubesheet.jpeg') }}" class="reference-image" alt="Tubesheet Reference">
                            </div>
                        </div>
                    </div>
                    <div id="ringFields_${bagNumber}" class="conditional-section">
                        <h3 style="margin-bottom: 15px; color: #1f3c88;"> Ring Type Specifications</h3>
                        <div class="form-group">
                            <label>Tubesheet Diameter *</label>
                            <div class="field-with-image">
                                <div class="field-wrapper">
                                    <input type="text" id="tubesheetDia_${bagNumber}" list="ringSizes_${bagNumber}" placeholder="Enter or select diameter (e.g. 160mm)">
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
                    document.getElementById(`collarFields_${bagNumber}`).classList.remove('active');
                    document.getElementById(`snapFields_${bagNumber}`).classList.remove('active');
                    document.getElementById(`ringFields_${bagNumber}`).classList.remove('active');
                    const type = radio.value;
                    document.getElementById(`${type === 'collar' ? 'collar' : type === 'snap' ? 'snap' : 'ring'}Fields_${bagNumber}`).classList.add('active');
                    loadBagSizes(bagNumber, type);
                });
            });
        }

        async function loadBagSizes(bagNumber, bagType) {
            try {
                const response = await fetch(`/api/sizes/${bagType}`);
                const data = await response.json();
                if (!data.success) return;
                let datalistId = bagType === 'collar' ? `collarSizes_${bagNumber}` : bagType === 'snap' ? `snapSizes_${bagNumber}` : `ringSizes_${bagNumber}`;
                const datalist = document.getElementById(datalistId);
                if (datalist) datalist.innerHTML = data.sizes.map(s => `<option value="${s.size_name}"></option>`).join('');
            } catch (error) { console.error('Error loading sizes:', error); }
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
                    const tubesheet = document.getElementById(`tubesheetData_${bagId}`).value.trim();
                    if (!tubesheet) { showMessage(`Please provide Tubesheet Data for Bag #${bagId}`, 'error'); return; }
                    bagData.tubesheet_data = tubesheet;
                } else if (bagType === 'ring') {
                    const dia = document.getElementById(`tubesheetDia_${bagId}`).value.trim();
                    if (!dia) { showMessage(`Please provide Tubesheet Diameter for Bag #${bagId}`, 'error'); return; }
                    bagData.tubesheet_dia = dia;
                }
                bags.push(bagData);
            }
            
            btn.disabled = true;
            btn.textContent = '⏳ Submitting...';
            loadingOverlay.classList.add('active');
            messageDiv.style.display = 'none';
            
            try {
                const response = await fetch('/api/submit-form/{{ token }}', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bags: bags, global_remarks: document.getElementById('globalRemarks').value || null })
                });
                const data = await response.json();
                loadingOverlay.classList.remove('active');
                if (data.success) {
                    document.querySelector('.content').innerHTML = `
                        <div style="text-align:center; padding:60px 20px;">
                            <div style="font-size:4rem; margin-bottom:20px;">✅</div>
                            <h2 style="color:#28a745; margin-bottom:10px;">Thank You!</h2>
                            <p style="color:#555; font-size:1.1em;">Your filter bag specification has been submitted successfully.</p>
                            <p style="color:#888; margin-top:10px; font-size:0.9em;">
                        </div>
                    `;
                } else {
                    showMessage('❌ ' + data.message, 'error');
                    btn.disabled = false;
                    btn.textContent = '📩 Submit All Specifications';
                }
            } catch (error) {
                loadingOverlay.classList.remove('active');
                showMessage('❌ Error: ' + error.message, 'error');
                btn.disabled = false;
                btn.textContent = '📩 Submit All Specifications';
            }
        });

        function showMessage(text, type) {
            const messageDiv = document.getElementById('message');
            messageDiv.style.display = 'block';
            messageDiv.className = `message ${type}`;
            messageDiv.innerHTML = text;
            messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
        .header { background: white; padding: 30px; border-radius: 15px 15px 0 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header h1 { color: #667eea; margin-bottom: 10px; }
        .back-link { display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 8px; margin-bottom: 20px; }
        .back-link:hover { background: #764ba2; }
        .submissions { background: white; padding: 30px; border-radius: 0 0 15px 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .submission-card { background: #f8f9ff; padding: 25px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #667eea; }
        .submission-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 15px; border-bottom: 2px solid #ddd; }
        .badge { padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: 600; }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-pending { background: #fff3cd; color: #856404; }
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
        <a href="/" class="back-link">← Back to Sender</a>
        <div class="header">
            <h1>📊 All Submissions</h1>
            <p>View all filter bag specification submissions</p>
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
                            <p style="color: #666; font-size: 14px; margin-top: 5px;">Created: {{ submission.created_at.strftime('%d %b %Y, %I:%M %p') }}</p>
                        </div>
                        <span class="badge {% if submission.submitted %}badge-success{% else %}badge-pending{% endif %}">
                            {% if submission.submitted %}✓ Submitted{% else %}⏳ Pending{% endif %}
                        </span>
                    </div>
                    <div class="detail-grid">
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
                            <div class="detail-label">📦 Quantity (Admin)</div>
                            <div class="detail-value">{{ submission.admin_quantity }}</div>
                        </div>
                        {% endif %}
                        {% if submission.admin_size %}
                        <div class="detail-item">
                            <div class="detail-label">📏 Size (Admin)</div>
                            <div class="detail-value">{{ submission.admin_size }}</div>
                        </div>
                        {% endif %}
                    </div>
                    {% if submission.submitted and submission.bag_type %}
                        <hr class="section-divider">
                        <p style="font-size: 13px; color: #888; margin-bottom: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Client Submission Details</p>
                        <div class="detail-grid">
                            <div class="detail-item">
                                <div class="detail-label">👤 Client Name</div>
                                <div class="detail-value">{{ submission.client_name or 'N/A' }}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">📧 Client Email</div>
                                <div class="detail-value">{{ submission.client_email or 'N/A' }}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">🛍️ Bag Type</div>
                                <div class="detail-value">{{ submission.bag_type.title() if submission.bag_type else 'N/A' }}</div>
                            </div>
                            {% if submission.bag_type == 'collar' %}
                            <div class="detail-item">
                                <div class="detail-label">⭕ Collar OD</div>
                                <div class="detail-value">{{ submission.collar_od or 'N/A' }}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">⭕ Collar ID</div>
                                <div class="detail-value">{{ submission.collar_id or 'N/A' }}</div>
                            </div>
                            {% elif submission.bag_type == 'snap' %}
                            <div class="detail-item">
                                <div class="detail-label">📌 Tubesheet Data</div>
                                <div class="detail-value">{{ submission.tubesheet_data or 'N/A' }}</div>
                            </div>
                            {% elif submission.bag_type == 'ring' %}
                            <div class="detail-item">
                                <div class="detail-label">💍 Tubesheet Diameter</div>
                                <div class="detail-value">{{ submission.tubesheet_dia or 'N/A' }}</div>
                            </div>
                            {% endif %}
                            <div class="detail-item">
                                <div class="detail-label">🕐 Submitted At</div>
                                <div class="detail-value">
                                    {% if submission.submitted_at %}{{ submission.submitted_at.strftime('%d %b %Y, %I:%M %p') }}{% else %}N/A{% endif %}
                                </div>
                            </div>
                        </div>
                        {% if submission.remarks %}
                        <div style="margin-top: 12px; background: white; border-radius: 8px; padding: 12px 15px; border: 1px solid #e0e0e0;">
                            <div class="detail-label">📝 Remarks</div>
                            <div class="detail-value" style="margin-top: 4px;">{{ submission.remarks }}</div>
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

# ==================== RUN APPLICATION ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Filter Bag Specification System - WITH MULTIPLE BAGS ✅")
    print("=" * 60)
    print(f"📧 Sender Email: {SENDER_EMAIL}")
    print(f"🌐 Server starting on http://127.0.0.1:5000")
    print("=" * 60)
    print("\n📍 Available Routes:")
    print("   - http://127.0.0.1:5000/ (Sender Interface)")
    print("   - http://127.0.0.1:5000/submissions (View All Submissions)")
    print("\n💡 Bug Fixes Applied:")
    print("   ✅ Form link never shows 'expired' before submission")
    print("   ✅ Edit & Re-Submit works correctly")
    print("   ✅ Re-submission cleans old child records (no duplicates)")
    print("   ✅ get_parent_submission() helper — reliable parent lookup")
    print("=" * 60)
    print("\n")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
