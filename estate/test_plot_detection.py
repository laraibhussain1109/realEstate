"""Geometry regression tests using real raster input, without a database or OCR service."""
import io
import json
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from .plot_detection import detect_plot_regions, detect_region_at_point


def synthetic_plan(mode='RGB'):
    image=Image.new(mode,(800,500),'white' if mode=='RGB' else (255,255,255,0))
    draw=ImageDraw.Draw(image)
    for box,color in [((50,50,180,190),'#16a34a'),((200,50,330,190),'#facc15'),((350,50,480,190),'#dc2626')]:
        draw.rectangle(box,fill=color,outline='black',width=3)
    draw.polygon([(50,250),(190,250),(190,300),(150,380),(50,380)],fill='white',outline='black',width=3)
    draw.rectangle((510,30,560,450),fill='#747b80',outline='black',width=2)
    return image


def contains(candidate,point):
    return cv2.pointPolygonTest(np.asarray(candidate['polygon'],np.float32),tuple(float(v) for v in point),False)>=0


class PlotDetectionGeometryTests(SimpleTestCase):
    def test_colored_and_white_irregular_plots_are_detected(self):
        result=detect_plot_regions(synthetic_plan(),{'ocr':False})
        self.assertEqual((result['width'],result['height']),(800,500))
        for point in [(100,100),(250,100),(400,100),(100,300)]:
            self.assertTrue(any(contains(candidate,point) for candidate in result['candidates']))
        irregular=next(c for c in result['candidates'] if contains(c,(100,300)))
        self.assertGreaterEqual(len(irregular['polygon']),5)
        self.assertFalse(contains(irregular,(180,370)))
        self.assertFalse(any(contains(c,(535,230)) for c in result['candidates']))
        self.assertTrue(all('status' not in candidate for candidate in result['candidates']))

    def test_jpeg_artifacts_do_not_prevent_closed_region_detection(self):
        data=io.BytesIO()
        synthetic_plan().save(data,format='JPEG',quality=68)
        data.seek(0)
        result=detect_plot_regions(data,{'ocr':False})
        for point in [(100,100),(250,100),(400,100),(100,300)]:
            self.assertTrue(any(contains(candidate,point) for candidate in result['candidates']))
        self.assertEqual(data.tell(),0)

    def test_monochrome_unfilled_boundaries_work_without_color_statuses(self):
        image=Image.new('RGB',(600,400),'white')
        draw=ImageDraw.Draw(image)
        draw.rectangle((30,30,180,180),outline='black',width=2)
        draw.polygon([(220,30),(390,30),(390,110),(330,180),(220,180)],outline='black',fill='white',width=2)
        result=detect_plot_regions(image,{'ocr':False})
        self.assertTrue(any(contains(c,(90,90)) for c in result['candidates']))
        self.assertTrue(any(contains(c,(260,90)) for c in result['candidates']))

    def test_transparent_background_is_composited_onto_white(self):
        result=detect_plot_regions(synthetic_plan('RGBA'),{'ocr':False})
        self.assertTrue(any(contains(c,(100,100)) for c in result['candidates']))
        self.assertFalse(any(contains(c,(700,450)) for c in result['candidates']))

    def test_large_image_coordinates_remain_in_original_coordinate_system(self):
        image=synthetic_plan().resize((3200,2000))
        result=detect_plot_regions(image,{'ocr':False,'max_dimension':1000})
        self.assertEqual((result['width'],result['height']),(3200,2000))
        self.assertLessEqual(max(result['processing_size']),1000)
        self.assertTrue(any(contains(c,(400,400)) for c in result['candidates']))
        for candidate in result['candidates']:
            for x,y in candidate['polygon']:
                self.assertTrue(0<=x<=3200 and 0<=y<=2000)

    def test_blank_page_has_no_plot_suggestions(self):
        result=detect_plot_regions(Image.new('RGB',(600,400),'white'),{'ocr':False})
        self.assertEqual(result['candidates'],[])
        self.assertTrue(result['warnings'])

    def test_click_recovers_a_region_and_rejects_road_or_background(self):
        image=synthetic_plan()
        result=detect_region_at_point(image,100,100,{'ocr':False})
        self.assertEqual(len(result['candidates']),1)
        self.assertTrue(contains(result['candidates'][0],(100,100)))
        for point in [(535,230),(10,10)]:
            result=detect_region_at_point(image,*point,{'ocr':False})
            self.assertEqual(result['candidates'],[])
            self.assertTrue(result['warnings'])

    def test_invalid_images_coordinates_and_options_are_rejected(self):
        with self.assertRaises(ValueError):detect_plot_regions(io.BytesIO(b'not an image'))
        for options in [{'max_dimension':30000},{'max_candidates':10000},{'min_area':float('nan')},{'ocr':'yes'}]:
            with self.subTest(options=options),self.assertRaises(ValueError):
                detect_plot_regions(synthetic_plan(),options)
        for point in [(-1,3),(900,2),(float('inf'),2),(True,3)]:
            with self.subTest(point=point),self.assertRaises(ValueError):
                detect_region_at_point(synthetic_plan(),*point,{'ocr':False})

    def test_candidates_are_capped_without_inventing_numbers(self):
        result=detect_plot_regions(synthetic_plan(),{'ocr':False,'max_candidates':2})
        self.assertEqual(len(result['candidates']),2)
        self.assertTrue(all(c['suggested_number'] is None for c in result['candidates']))

    @mock.patch('estate.plot_detection.shutil.which',return_value=None)
    def test_missing_optional_ocr_keeps_boundary_detection_usable(self,which):
        result=detect_plot_regions(synthetic_plan())
        self.assertGreaterEqual(len(result['candidates']),4)
        self.assertTrue(all(c['suggested_number'] is None for c in result['candidates']))
        self.assertTrue(any('number' in warning.lower() for warning in result['warnings']))

    def test_reference_plan_recovers_all_known_plot_interiors_but_not_roads_or_park(self):
        assets=Path(__file__).resolve().parent/'static/estate/images'
        result=detect_plot_regions(assets/'govindpuram-plan.png',{'ocr':False})
        geometry=json.loads((assets/'demo-geometry.json').read_text())
        self.assertEqual(len(geometry),63)
        for plot in geometry:
            center=np.mean(np.asarray(plot['polygon'],np.float32),axis=0)
            self.assertTrue(any(contains(candidate,center) for candidate in result['candidates']),plot['number'])
        # Unnumbered parcels can also be candidates: do not assert a brittle
        # total candidate count or imply the reconstructed reference is a survey.
        for point in [(160,300),(400,490),(780,400),(495,614),(420,710)]:
            self.assertFalse(any(contains(c,point) for c in result['candidates']))
        self.assertEqual(detect_region_at_point(assets/'govindpuram-plan.png',780,400,{'ocr':False})['candidates'],[])
        narrow=detect_region_at_point(assets/'govindpuram-plan.png',215,432,{'ocr':False})
        self.assertEqual(len(narrow['candidates']),1)
        self.assertTrue(contains(narrow['candidates'][0],(215,432)))
