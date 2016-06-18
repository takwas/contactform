"""
contact_form
~~~~~~~~~~~~

Contact form app for static websites

:author: Krohx Technologies (krohxinc@gmail.com)
:copyright: (c) 2016 by Krohx Technologies
:license: see LICENSE for details.
"""

# standard lib imports
import os
import logging

# library imports
from flask import Flask, redirect, url_for, redirect, request, render_template
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from lepl.apps.rfc3696 import Email # for email validation

import config

app = Flask(__name__)
app.config.from_object(config)

# Instantiate Flask extensions
mail = Mail(app)
db = SQLAlchemy(app)

import db_ops # circular import guard
db.create_all()

# email validator
validator = Email()

# setup logging
#logging.basicConfig(format='%(asctime)s | %(levelname)s: %(message)s', datefmt='%a %b, %Y (%I:%M:%S %p)', filename='app_log.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)
if app.config.get('DEBUG', False):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('app_log.log')
formatter = logging.Formatter('%(asctime)s | %(levelname)s:\t%(message)s', datefmt='%a %b, %Y (%I:%M:%S %p)')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def log_newline(num_lines=1):
    for i in range(num_lines):
        logger.info('\n')


def log_break():
    logger.info('\n\n---\n\n')


def is_valid_url(url):
    import requests as r
    page = r.get(url)
    if page.status_code == 200:
        page.content

    return False


def validate_email(email):
    if validator(email):
        return True
    else:
        raise EmailValidationError


def send_email(app, recp, message, sender=None, subject="Someone sent a message from your website."):

    # if recipient is passed as a string,
    # remove whitespaces and commas, splitting
    # the string into a list of recipients
    if isinstance(recp, str) or isinstance(recp, unicode):
        recp = [k.strip() for k in recp.split(',')]
    
    if sender is None:
        sender=config.MAIL_SENDER
    try:
        mail_msg = Message(
            subject=subject,
            recipients=recp,
            html=message,
            sender=sender
        )

        mail.send(mail_msg)
        return True
    except Exception, e:
        #print 'Error formatting and sending email!' # DEBUG
        logger.error('Error formatting and sending email!', exc_info=True)
        return False


def format_msg_html(**kwargs):
    param_dict = dict()

    param_dict['name'] = kwargs.get('name', 'None').title()
    param_dict['email'] = kwargs.get('email', 'None')
    param_dict['phone'] = kwargs.get('phone', 'None')
    subject = kwargs.get('subject', 'No subject')
    message = kwargs.get('message', 'No message')

    return render_template(
        'email_html.html',
        param_dict=param_dict,
        subject=subject,
        message=message
    )


class EmailValidationError(Exception):
    pass


@app.route('/index/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'POST':
        log_newline(2)
        logger.info('New contact-us form received!')
        logger.info('Site: %s', str(request.referrer))
        form_dict = dict(request.form)
        logger.info('Form: %s', str(form_dict))

        data_fields = ['name', 'phone', 'email', 'subject', 'message']
        data = dict()
        
        try:
            for k,v in form_dict.iteritems():
                if k in data_fields and bool(v[0]):
                    data[k] = unicode(v[0]).decode('utf-8')
            logger.info('Form->Dict Serialize: %s', str(data))
        except Exception, e:
            #print 'Failed to handle form:\n\t%r' % request.form # DEBUG
            logger.error('Serialize Fail!', exc_info=True)
            return render_template('failure.html',
                goto=request.referrer,
                message="There was an error. Your message was not sent. Please try again."
            )

        if data.get('email'):
            print '\nREFERRER %s\n' % request.referrer # DEBUG
            site = db_ops.ret_val(db_ops.Site, dict(url=request.referrer))
            #message = '{subj}\n\n{msg}'.format(subj=data.get('subject', ''), msg=data.get('message', '')).strip()
            message = format_msg_html(**data)
            if site is not None:
                logger.info('Site found in records!')
                recp = site.email
                if send_email(app, recp=recp, message=message, sender=config.MAIL_SENDER, subject="ContactForm: New message from your website."):
                    logger.info('Email sent to %s', str(data.get('email')))
                    return render_template('success.html',
                        goto=request.referrer,
                        message="Your message was sent successfully."
                    )
            else:
                logger.error('Site not found in records!')

        logger.error('Email not sent!\n\t%s', str(request.form))
        log_break()
        #print 'Error! Not sending mail...\n\t%r' % request.form # DEBUG
        return render_template('failure.html',
            goto=request.referrer,
            message="There was an error. Your message was not sent. Please try again."
        )

    logger.info('Home page hit, redirecting to signup...')
    log_newline()
    return redirect(url_for('signup'))


@app.route('/signup/', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':
        log_newline(2)
        logger.info('New signup form received!')
        form_dict = dict(request.form)
        logger.info('Form: %s', str(form_dict))
        param_dict = dict()

        try:
            param_dict['name'] = form_dict.get('name')[0]
            param_dict['url'] = form_dict.get('url')[0]
            param_dict['email'] = form_dict.get('email')[0]
            param_dict['password'] = form_dict.get('password')[0]
            #verifyurl
            # Need to cleanup this code
            if validate_email(param_dict.get('email', 'invalid_email')):
                if db_ops.insert_val(db_ops.Site, param_dict, rollback_on_fail=True):
                    logger.info('New user subscribed!')
                    return render_template('success.html',
                        goto=request.referrer,
                        message="Thank you. Your site has been registered with us."
                    )
        except Exception, e:
            #print 'Error! Failed to register new site:\n\t%r' % request.form # DEBUG
            logger.error('Error signing-up new user!', exc_info=True)
            return render_template('failure.html',
                goto=request.referrer,
                message="There was an error. Your registration was unsuccessful. Please try again."
            )
        finally:
            log_break()
            param_dict.clear()

    return render_template('signup.html')


@app.errorhandler(500)
def server_error(error):
    return redirect(request.referrer), 500


@app.errorhandler(404)
def _404(error):
    return redirect(request.referrer), 404


if __name__ == '__main__':
    app.run()