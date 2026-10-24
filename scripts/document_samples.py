"""Synthetic document-like layouts. No real identities, logos, signatures or scans."""
import io

from PIL import Image, ImageDraw, ImageFont


# Expected sensitive VALUES, not the public field labels.
DOCUMENTS = {
    'aadhaar': [('Name', 'Demo Sample', 'PERSON'), ('DOB', '01/02/1990', 'DATE_OF_BIRTH'),
                ('Address', '17 Example Lane', 'ADDRESS'), ('Aadhaar', '2345 6789 0123', 'POSSIBLE_ID')],
    'pan': [('Name', 'Demo Sample', 'PERSON'), ('Father name', 'Example Parent', 'PERSON'),
            ('DOB', '01/02/1990', 'DATE_OF_BIRTH'), ('PAN', 'ABCDE1234F', 'PAN')],
    'passport': [('Given name', 'Demo Sample', 'PERSON'), ('Surname', 'Example', 'PERSON'),
                 ('Passport number', 'Z1234567', 'POSSIBLE_ID'), ('DOB', '01/02/1990', 'DATE_OF_BIRTH'),
                 ('', 'P<ZZZDEMO<<SAMPLE<<<<<<<<<<<<<<<<<<<<<<<<<<<', 'POSSIBLE_ID')],
    'driving_licence': [('Name', 'Demo Sample', 'PERSON'), ('Driving licence number', 'MH1420260012345', 'POSSIBLE_ID'),
                        ('Address', '17 Example Lane', 'ADDRESS')],
    'voter_id': [('Name', 'Demo Sample', 'PERSON'), ('EPIC number', 'XYZ1234567', 'POSSIBLE_ID'),
                 ('Address', '17 Example Lane', 'ADDRESS')],
    'ration_card': [('Name', 'Demo Sample', 'PERSON'), ('Ration number', 'RC2026001234', 'POSSIBLE_ID'),
                    ('Address', '17 Example Lane', 'ADDRESS')],
    'bank_statement': [('Account holder name', 'Demo Sample', 'PERSON'),
                       ('Account number', '34567890123456', 'POSSIBLE_ID'), ('IFSC', 'DEMO0001234', 'FINANCIAL_ID'),
                       ('Address', '17 Example Lane', 'ADDRESS')],
    'payment_card': [('Card holder name', 'Demo Sample', 'PERSON'),
                     ('', '4111 1111 1111 1111', 'POSSIBLE_ID')],
    'payslip': [('Employee name', 'Demo Sample', 'PERSON'), ('Employee ID', 'EMP001234', 'POSSIBLE_ID'),
                ('UAN', '100200300400', 'POSSIBLE_ID'), ('Net salary', '45000.00', 'FINANCIAL_INFO')],
    'medical_report': [('Patient name', 'Demo Sample', 'PERSON'), ('UHID', 'DEMO001234', 'POSSIBLE_ID'),
                       ('Diagnosis', 'Synthetic condition', 'HEALTH_INFO'), ('Blood group', 'AB positive', 'HEALTH_INFO')],
    'insurance': [('Name', 'Demo Sample', 'PERSON'), ('Policy number', 'POL2026001234', 'POSSIBLE_ID'),
                  ('DOB', '01/02/1990', 'DATE_OF_BIRTH')],
    'utility_bill': [('Customer name', 'Demo Sample', 'PERSON'), ('Consumer number', 'CON2026001234', 'POSSIBLE_ID'),
                     ('Billing address', '17 Example Lane', 'ADDRESS')],
    'invoice': [('Customer name', 'Demo Sample', 'PERSON'), ('Shipping address', '17 Example Lane', 'ADDRESS'),
                ('GSTIN', '27ABCDE1234F1Z5', 'POSSIBLE_ID'), ('Email', 'demo@example.org', 'EMAIL')],
    'education_certificate': [('Student name', 'Demo Sample', 'PERSON'),
                              ('Admission number', 'ADM2026001234', 'POSSIBLE_ID'), ('DOB', '01/02/1990', 'DATE_OF_BIRTH')],
    'vehicle_registration': [('Name', 'Demo Sample', 'PERSON'),
                             ('Registration number', 'MH14DE1234', 'POSSIBLE_ID'), ('Address', '17 Example Lane', 'ADDRESS')],
    'resume': [('Full name', 'Demo Sample', 'PERSON'), ('Email', 'demo@example.org', 'EMAIL'),
               ('Mobile', '9876543210', 'PHONE'), ('Address', '17 Example Lane', 'ADDRESS')],
    'benign_invoice': [('Invoice number', 'INV2026001234', None), ('Invoice date', '25/10/2026', None),
                       ('Quantity', '12', None), ('Total amount', '1500.00', None)],
}


def render_document(name):
    font = ImageFont.load_default(size=30)
    image = Image.new('RGB', (1400,850), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((40,30), 'SYNTHETIC TEST DOCUMENT', font=font, fill='black')
    header = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
    tsv, targets = header, []
    for line, (label, value, entity) in enumerate(DOCUMENTS[name], 2):
        y = 70 + line * 95
        prefix = label + ': ' if label else ''
        draw.text((40,y), prefix + value, font=font, fill='black')
        x = 40 + draw.textlength(prefix, font=font)
        box = draw.textbbox((x,y), value, font=font)
        if entity:
            targets.append((entity, box))
        cursor = 40
        for index, word in enumerate((prefix + value).split(), 1):
            left, top, right, bottom = draw.textbbox((cursor,y), word, font=font)
            left, top, right, bottom = int(left), int(top), int(right+1), int(bottom+1)
            tsv += f'5\t1\t1\t1\t{line}\t{index}\t{left}\t{top}\t{right-left}\t{bottom-top}\t96\t{word}\n'
            cursor += draw.textlength(word+' ', font=font)
    output = io.BytesIO(); image.save(output, format='PNG')
    return output.getvalue(), tsv, targets
