"""
OLED Display Module for Speech Analyzer
Handles displaying prompts and analysis results on an SSD1306 OLED display
"""

try:
    import board
    import digitalio
    import adafruit_ssd1306
    BOARD_AVAILABLE = True
except ImportError:
    # Board module not available (running on computer without hardware)
    BOARD_AVAILABLE = False
    print("Board module not available - OLED display will be simulated")

from PIL import Image, ImageDraw, ImageFont
import time
import math


class OLEDDisplay:
    def __init__(self, width=128, height=64, sda_pin=None, scl_pin=None):
        """
        Initialize the OLED display

        Args:
            width: Display width in pixels (default 128)
            height: Display height in pixels (default 64)
            sda_pin: I2C SDA pin (default None - uses board.D5 if hardware available)
            scl_pin: I2C SCL pin (default None - uses board.D23 if hardware available)
        """
        self.width = width
        self.height = height
        self.hardware_available = BOARD_AVAILABLE

        if self.hardware_available:
            # Initialize I2C connection
            i2c = board.I2C()  # uses board.SCL and board.SDA

            # Create SSD1306 OLED class
            self.display = adafruit_ssd1306.SSD1306_I2C(width, height, i2c)

            # Clear the display
            self.clear_display()
        else:
            print("OLED hardware not available - running in simulation mode")
            self.display = None

        # Load default font
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        except:
            # Fallback to default font if DejaVu font is not available
            self.font = ImageFont.load_default()

        try:
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
        except:
            self.small_font = ImageFont.load_default()
    
    def clear_display(self):
        """Clear the OLED display"""
        if self.hardware_available and self.display:
            self.display.fill(0)
            self.display.show()
    
    def display_text(self, text, x=0, y=0, font=None):
        """
        Display text at specific coordinates

        Args:
            text: Text to display
            x: X coordinate
            y: Y coordinate
            font: Font to use (optional)
        """
        if font is None:
            font = self.font

        # Create blank image for drawing
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)

        # Draw text
        draw.text((x, y), text, font=font, fill=255)

        # Display image if hardware is available
        if self.hardware_available and self.display:
            self.display.image(image)
            self.display.show()
        else:
            # Simulate display in console
            print(f"OLED Display: {text}")
    
    def display_scrollable_text(self, text, y=0, font=None, scroll_speed=0.5):
        """
        Display text that scrolls if it doesn't fit on the screen

        Args:
            text: Text to display
            y: Y coordinate for text
            font: Font to use (optional)
            scroll_speed: Speed of scrolling (lower is faster)
        """
        if font is None:
            font = self.font

        # Create blank image for drawing
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)

        # Calculate text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # If text fits, just display normally
        if text_width <= self.width:
            draw.text((0, y), text, font=font, fill=255)
            if self.hardware_available and self.display:
                self.display.image(image)
                self.display.show()
            else:
                # Simulate display in console
                print(f"OLED Display: {text}")
            return

        # If text doesn't fit, create scrolling effect
        # Create a larger image to hold the full text
        scroll_image = Image.new("1", (text_width + self.width, self.height))
        scroll_draw = ImageDraw.Draw(scroll_image)
        scroll_draw.text((0, y), text, font=font, fill=255)

        # Scroll the text
        if self.hardware_available and self.display:
            for offset in range(0, text_width + self.width, 2):
                # Crop the scrolling image to fit the display
                cropped = scroll_image.crop((offset, 0, offset + self.width, self.height))
                self.display.image(cropped)
                self.display.show()
                time.sleep(scroll_speed)
        else:
            # Simulate scrolling in console
            print(f"OLED Display (Scrolling): {text[:50]}{'...' if len(text) > 50 else ''}")
    
    def display_prompt_and_ratings(self, prompt_text, analysis_results=None):
        """
        Display the prompt text and analysis ratings on the OLED
        
        Args:
            prompt_text: The prompt text to display
            analysis_results: Dictionary with analysis results (optional)
        """
        # Create blank image for drawing
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        
        # Display prompt text at top (first line)
        prompt_lines = self._wrap_text(prompt_text, self.width, self.font)
        
        # If there's only one line and it fits, display it directly
        if len(prompt_lines) == 1 and len(prompt_lines[0]) * 8 <= self.width:
            draw.text((0, 0), prompt_lines[0], font=self.font, fill=255)
        else:
            # If multiple lines or too long, show first part with indicator
            if prompt_lines:
                # Display first part of the prompt
                display_text = prompt_lines[0][:int(self.width/8)-3] + "..." if len(prompt_lines[0]) * 8 > self.width else prompt_lines[0]
                draw.text((0, 0), display_text, font=self.font, fill=255)
                
                # Indicate there's more text by showing a scrolling effect
                if len(prompt_lines) > 1 or len(prompt_lines[0]) * 8 > self.width:
                    self._scroll_prompt_text(prompt_text)
        
        # Display ratings if provided
        if analysis_results:
            y_pos = 15  # Start below the prompt text
            
            # Display average score if possible
            numeric_scores = [score for score in analysis_results.values() if isinstance(score, (int, float))]
            if numeric_scores:
                avg_score = sum(numeric_scores) / len(numeric_scores)
                avg_text = f"Avg: {avg_score:.1f}/10"
                draw.text((0, y_pos), avg_text, font=self.font, fill=255)
                y_pos += 12
            
            # Display individual scores
            for aspect, score in analysis_results.items():
                if isinstance(score, (int, float)):
                    score_text = f"{aspect[:6]}: {score:.1f}"  # Truncate aspect name
                    draw.text((0, y_pos), score_text, font=self.small_font, fill=255)
                    y_pos += 10
                    
                    # Stop if we're running out of space
                    if y_pos > self.height - 10:
                        break
                elif isinstance(score, str):
                    score_text = f"{aspect[:6]}: {score}"  # Truncate aspect name
                    draw.text((0, y_pos), score_text, font=self.small_font, fill=255)
                    y_pos += 10
                    
                    # Stop if we're running out of space
                    if y_pos > self.height - 10:
                        break
        
        # Display the image if hardware is available
        if self.hardware_available and self.display:
            self.display.image(image)
            self.display.show()
        else:
            # Simulate display in console
            print(f"OLED Display - Prompt: {prompt_text[:50]}{'...' if len(prompt_text) > 50 else ''}")
            if analysis_results:
                print(f"OLED Display - Results: {analysis_results}")
    
    def _wrap_text(self, text, max_width, font):
        """
        Wrap text to fit within the display width
        
        Args:
            text: Text to wrap
            max_width: Maximum width in pixels
            font: Font to use for measuring
            
        Returns:
            List of wrapped lines
        """
        draw = ImageDraw.Draw(Image.new("1", (1, 1)))
        lines = []
        words = text.split()
        
        if not words:
            return [""]
        
        current_line = words[0]
        
        for word in words[1:]:
            # Test if adding this word would exceed the max width
            test_line = current_line + " " + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            test_width = bbox[2] - bbox[0]
            
            if test_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        
        lines.append(current_line)
        return lines
    
    def _scroll_prompt_text(self, prompt_text):
        """
        Internal method to scroll the prompt text if it doesn't fit
        
        Args:
            prompt_text: The prompt text to scroll
        """
        # Create a temporary larger image for scrolling
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        
        # Calculate text dimensions
        bbox = draw.textbbox((0, 0), prompt_text, font=self.font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= self.width:
            return  # No need to scroll if it fits
        
        # Create a wider image to accommodate scrolling
        scroll_image = Image.new("1", (text_width + self.width, self.height))
        scroll_draw = ImageDraw.Draw(scroll_image)
        scroll_draw.text((0, 0), prompt_text, font=self.font, fill=255)
        
        # Scroll the text across the display
        if self.hardware_available and self.display:
            for offset in range(0, text_width, 2):
                cropped = scroll_image.crop((offset, 0, offset + self.width, self.height))
                self.display.image(cropped)
                self.display.show()
                time.sleep(0.1)  # Adjust speed as needed
            
            # Pause at the end of scrolling
            time.sleep(0.5)
        else:
            # Simulate scrolling in console
            print(f"OLED Display (Scrolling): {prompt_text[:50]}{'...' if len(prompt_text) > 50 else ''}")
    
    def display_startup_message(self):
        """Display a startup message on the OLED"""
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)

        # Draw a simple logo/text
        draw.text((20, 20), "Speech", font=self.font, fill=255)
        draw.text((20, 35), "Analyzer", font=self.font, fill=255)
        draw.text((10, 50), "Ready...", font=self.small_font, fill=255)

        if self.hardware_available and self.display:
            self.display.image(image)
            self.display.show()
        else:
            print("OLED Display - Startup: Speech Analyzer Ready...")
    
    def display_processing_message(self):
        """Display a processing message on the OLED"""
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)

        draw.text((10, 25), "Processing", font=self.font, fill=255)
        draw.text((25, 40), "Audio...", font=self.font, fill=255)

        if self.hardware_available and self.display:
            self.display.image(image)
            self.display.show()
        else:
            print("OLED Display - Processing: Audio...")
    
    def display_results_summary(self, analysis_results):
        """
        Display a summary of results on the OLED

        Args:
            analysis_results: Dictionary with analysis results
        """
        image = Image.new("1", (self.width, self.height))
        draw = ImageDraw.Draw(image)

        # Calculate average score
        numeric_scores = [score for score in analysis_results.values() if isinstance(score, (int, float))]
        if numeric_scores:
            avg_score = sum(numeric_scores) / len(numeric_scores)

            # Display average score prominently
            avg_str = f"Avg: {avg_score:.1f}/10"
            draw.text((10, 10), avg_str, font=self.font, fill=255)

            # Draw a simple bar representing the score
            bar_width = int((avg_score / 10) * 100)
            draw.rectangle((10, 30, 10 + bar_width, 40), outline=255, fill=255)

            # Add labels
            draw.text((10, 45), "Score:", font=self.small_font, fill=255)

        if self.hardware_available and self.display:
            self.display.image(image)
            self.display.show()
        else:
            # Simulate display in console
            if numeric_scores:
                avg_score = sum(numeric_scores) / len(numeric_scores)
                print(f"OLED Display - Results Summary: Avg Score: {avg_score:.1f}/10")


# Example usage when running this file directly
if __name__ == "__main__":
    # Initialize the OLED display
    oled = OLEDDisplay()
    
    # Display a startup message
    oled.display_startup_message()
    time.sleep(2)
    
    # Example prompt text
    prompt = "This is a sample prompt text that might be quite long and need scrolling to fit on the OLED display."
    
    # Example analysis results
    results = {
        'fluency': 7.5,
        'pronunciation': 8.2,
        'articulation': 7.8,
        'pace': 6.9,
        'clarity': 8.0,
        'confidence': 7.3,
        'emotion': 'positive'
    }
    
    # Display the prompt and ratings
    oled.display_prompt_and_ratings(prompt, results)
    time.sleep(5)
    
    # Clear the display
    oled.clear_display()