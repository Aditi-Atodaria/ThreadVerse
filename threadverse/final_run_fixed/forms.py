from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, HiddenField, TelField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp


class LoginForm(FlaskForm):
    email          = StringField('Email',    validators=[DataRequired(), Email()])
    password       = PasswordField('Password', validators=[DataRequired()])
    selected_role  = HiddenField('Role',     default='customer')
    preferred_store = HiddenField('Store')
    next           = HiddenField()


class RegisterForm(FlaskForm):
    name    = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email   = StringField('Email',     validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    contact_number = StringField('Contact Number', validators=[
        DataRequired(),
        Regexp(r'^\+?[0-9]{10,15}$', message='Enter a valid 10–15 digit phone number')
    ])
    otp         = StringField('OTP',       validators=[Optional(), Length(min=6, max=6)])
    role        = SelectField('Account Type', choices=[
                    ('customer', '🛍️ Shop — Browse & buy fashion'),
                    ('vendor',   '🏪 Sell — List products on ThreadVerse')
                  ])
    shop_name   = StringField('Shop Name', validators=[Optional()])
    verification_doc = FileField('Verification Document', validators=[
        FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 'PDF or image files only')
    ])
