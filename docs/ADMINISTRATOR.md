# Administrator handbook

## Sign in

Open `/admin/` and use the account created during installation. Visitors browse the public site without signing in. Only trusted staff should have an administrator account. A superuser can add staff under Users, check **Staff status**, and assign permissions for the records that person should manage.

Run `python manage.py setup_roles` during installation to create the Project Manager, Sales Manager and Content Editor groups. A superuser can assign these groups to staff, then review the permissions before granting access.

## Company information

Open **Site settings** to update the company name, contact numbers, WhatsApp number, office address, mission, vision, homepage wording and other available site fields. Save and check the public page. Use verified information. The brochure's generic founding-year and customer endorsement are not evidence of Plot Matrix's history or customer feedback.

Homepage section records let you edit section titles and descriptions, turn a supported section on or off, and change its display order. Keep the existing section **key** unchanged: only the application's supported section keys render their corresponding content. A published Hero Banner takes priority over the company settings hero; unpublish it to return to the company settings hero image and text.

## Add a location

1. Add a state.
2. Add a city linked to that state.
3. Add an area linked to the city, with a unique URL slug, optional image and description.
4. Enable the area when it is ready to show publicly.

The public location counts come from published projects. An empty area is not a claim that a development is available there.

## Create a project

1. Add a project and choose its area.
2. Enter its name, URL slug, code, address and descriptions.
3. Upload a cover image, brochure and any public documents. Enter factual sizes, roads and completion information only when confirmed.
4. Add real amenities. Enter a Google Maps destination link; an embeddable URL has its own field.
5. Enter regulatory information only if it is verified. Add any required project disclaimer.
6. Keep the project **Draft** while preparing it. Select **Published** when the content is verified. **Archived** removes it from public browsing.

Do not publish demonstration inventory as a genuine offer. Demo projects must retain their DEMO label.

## Upload a master plan

Add a project layout, choose the project and upload a clear raster image. JPEG, PNG and WebP are suitable. Use a new layout revision when a source image changes; do not replace the background beneath existing polygons. Keep the new revision as a draft until its boundaries and labels are checked. Activate the correct verified revision for public viewing.

PDFs can be provided as downloadable project documents. Where the upload interface accepts a PDF for the layout, follow its conversion guidance. Otherwise export the relevant PDF page to a good-quality PNG first. Conversion is an explicit preparation step, not work performed on every page visit. PDF document uploads must be ordinary, unencrypted PDFs with no scripts, forms or embedded files. If a legitimate document is rejected, export a plain copy from a trusted source; do not disable validation. File validation is not a malware-scanning guarantee.

## Draw plot boundaries

1. Follow the layout's **Open visual editor** link.
2. Zoom or pan to the plot.
3. Select the draw tool and click each boundary corner. Close the shape using the editor's close/finish control.
4. Enter the real plot number, area and unit, optional dimensions, direction, road width and public price.
5. Choose **Available**, **Booked**, **Sold**, or an appropriate non-sale status.
6. Save, then confirm the label and boundary line up with the source image.

Select an existing polygon to edit its details or move its corner handles. Undo/redo reverses local drawing changes; save when the geometry is correct. Search locates a plot. Delete requires confirmation. Label positions can be adjusted independently of the plot boundary. Use bulk status changes only after checking all selected plots.

A plot area and its length/width are different measurements. Choose the right area unit rather than entering an approximate conversion. Internal remarks stay private. Public remarks appear to visitors.

## Change availability

Select the plot in admin or the editor, choose its new status and save. The site calculates totals from stored records. Available is green, Booked yellow and Sold red; the viewer also names the status in text. Open pages refresh availability periodically, and a full page refresh fetches current data immediately. The status history records the change for accountability.

A website enquiry is a lead; it does not mark a plot booked. Only authorized staff should confirm booking or sale status.

## Gallery and testimonials

Upload gallery images, assign a project/area/category, write useful alternative text and a caption, and select publication/visibility controls. Check the image appears in the correct filter. Avoid using illustrative brochure imagery as evidence of completed site work.

Add testimonials only with the customer's approval and a real quote. Leave them unpublished until reviewed. Empty testimonial sections are hidden rather than filled with fictional endorsements.

## Enquiries and site visits

Open **Enquiries** to see contact and site visit requests. Check the project and plot context before responding. Update the lead's workflow status and private notes as your team follows up. An enquiry does not guarantee availability, price or a confirmed appointment. Contact the visitor to confirm a visit time.

## Maintenance

Back up the database and uploaded files before major changes. Keep the backup out of the public media directory. Periodically verify that project documents, phone/WhatsApp actions, directions and public contact forms still work. Remove old staff access promptly. Ask the deployment administrator to install compatible security updates and run the automated checks before reloading production.
