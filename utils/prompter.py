"""
Text prompter module for generating reading passages based on duration
"""
import random
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TextPrompter:
    """
    A class to generate text prompts for speech practice based on recording duration
    """
    
    # Sample texts organized by approximate reading time (in seconds)
    SAMPLE_TEXTS = {
        5: [  # ~5 seconds to read
            "Hello, how are you today?",
            "The weather is nice outside.",
            "I enjoy learning new things.",
            "Technology is advancing rapidly.",
            "Reading improves vocabulary skills."
        ],
        10: [  # ~10 seconds to read
            "The quick brown fox jumps over the lazy dog. This classic sentence contains every letter of the alphabet.",
            "Practice makes perfect when learning a new language. Consistent effort leads to improvement over time.",
            "Public speaking requires confidence and preparation. Preparation helps reduce anxiety and improve delivery.",
            "Effective communication involves listening as well as speaking. Good listeners often become better speakers.",
            "Language learning is a gradual process that requires patience. Regular practice helps develop fluency."
        ],
        15: [  # ~15 seconds to read
            "The art of public speaking combines confidence, clarity, and connection with your audience. Great speakers practice regularly and focus on their message.",
            "Learning a new language opens doors to different cultures and opportunities. Dedication and consistent practice are key to achieving fluency.",
            "Communication skills are essential in both personal and professional relationships. Clear expression helps prevent misunderstandings and builds trust.",
            "Confident speaking comes from preparation and practice. Understanding your topic and organizing your thoughts beforehand helps deliver a strong presentation.",
            "Vocabulary expansion happens naturally through reading and conversation. Exposure to diverse topics enriches your ability to express ideas."
        ],
        20: [  # ~20 seconds to read
            "Developing strong communication skills takes time and dedication. Regular practice with varied materials helps speakers become more confident and articulate. Focus on pronunciation, pacing, and clarity to enhance your effectiveness.",
            "Public speaking anxiety affects many people, but preparation can significantly reduce nervousness. Practice your speech multiple times, know your material, and remember that audiences appreciate authenticity over perfection.",
            "Effective presentations combine clear organization with engaging delivery. Start with a strong opening, support your points with evidence, and conclude with a memorable summary. Visual aids can enhance understanding when used appropriately.",
            "Language learning benefits from exposure to diverse content and consistent practice. Reading books, listening to podcasts, and engaging in conversations all contribute to improved fluency and comprehension. Set realistic goals and celebrate progress along the way.",
            "Building confidence in speaking requires patience and positive self-talk. Focus on your strengths, acknowledge improvement, and view mistakes as learning opportunities. Remember that even experienced speakers continue to grow and develop their skills."
        ],
        30: [  # ~30 seconds to read
            "The foundation of effective communication lies in understanding your audience and purpose. Successful speakers adapt their message, tone, and delivery to connect with listeners. Preparation involves researching your topic, organizing content logically, and anticipating questions. Confidence grows with practice, so seek opportunities to speak in low-stakes environments before tackling more challenging situations. Remember that even experienced communicators continue to refine their skills throughout their careers.",
            "Mastering a new language requires dedication, patience, and consistent practice. Immersion experiences accelerate learning, but structured study remains important for grammar and vocabulary development. Set achievable goals, track your progress, and celebrate milestones along the way. Engaging with native speakers and consuming authentic materials enhances comprehension and cultural understanding. Remember that language learning is a journey with natural ups and downs.",
            "Public speaking skills benefit from understanding the fundamentals of rhetoric and audience psychology. Effective speakers establish credibility, demonstrate empathy, and support arguments with evidence. Preparation includes knowing your material, practicing aloud, and considering logistics. Managing anxiety involves breathing techniques, positive visualization, and focusing on your message rather than yourself. Growth comes through experience and reflection on performances.",
            "Professional development in communication encompasses both verbal and nonverbal elements. Body language, eye contact, and vocal variety significantly impact how messages are received. Active listening skills complement speaking abilities, creating more meaningful exchanges. Networking opportunities allow practice in informal settings while building relationships. Continuous learning through workshops, courses, and feedback accelerates improvement and builds confidence.",
            "Building speaking confidence involves gradual exposure to increasingly challenging situations. Start with familiar audiences and simple topics, then expand to new contexts. Preparation reduces anxiety, so outline key points and practice transitions. Accept that nervousness is normal and often enhances performance when managed well. Focus on serving your audience rather than impressing them, which creates authentic connections and reduces pressure."
        ]
    }
    
    # Fallback texts for durations not specifically categorized
    GENERAL_TEXTS = [
        "The quick brown fox jumps over the lazy dog. This classic sentence contains every letter of the alphabet.",
        "Practice makes perfect when learning a new language. Consistent effort leads to improvement over time.",
        "Public speaking requires confidence and preparation. Preparation helps reduce anxiety and improve delivery.",
        "Effective communication involves listening as well as speaking. Good listeners often become better speakers.",
        "Language learning is a gradual process that requires patience. Regular practice helps develop fluency.",
        "The art of public speaking combines confidence, clarity, and connection with your audience. Great speakers practice regularly and focus on their message.",
        "Learning a new language opens doors to different cultures and opportunities. Dedication and consistent practice are key to achieving fluency.",
        "Communication skills are essential in both personal and professional relationships. Clear expression helps prevent misunderstandings and builds trust."
    ]

    @staticmethod
    def estimate_reading_time(text):
        """
        Estimate reading time in seconds based on average reading speed
        Average reading speed is about 150-200 words per minute for English
        We'll use 175 wpm as a baseline (~3 words per second)
        """
        word_count = len(text.split())
        # 175 words per minute = ~2.9 words per second
        estimated_seconds = max(3, word_count / 2.9)  # Minimum 3 seconds
        return round(estimated_seconds, 1)

    def get_prompt_text(self, duration):
        """
        Get an appropriate text prompt based on the requested duration
        :param duration: Expected recording duration in seconds
        :return: A text prompt for the user to read
        """
        logger.info(f"Getting prompt for duration: {duration} seconds")
        
        # Find the closest duration category
        available_durations = sorted(self.SAMPLE_TEXTS.keys())
        
        # Find the best matching category based on duration
        best_match = available_durations[0]  # Start with shortest
        min_diff = abs(duration - best_match)
        
        for dur in available_durations:
            diff = abs(duration - dur)
            if diff < min_diff:
                min_diff = diff
                best_match = dur
        
        # Select a random text from the best matching category
        selected_texts = self.SAMPLE_TEXTS.get(best_match, self.GENERAL_TEXTS)
        prompt = random.choice(selected_texts)
        
        # Double-check the estimated reading time is close to requested duration
        estimated_time = self.estimate_reading_time(prompt)
        logger.info(f"Selected prompt estimated reading time: {estimated_time}s for requested: {duration}s")
        
        # If the estimated time is significantly different, try to find a better match
        if abs(estimated_time - duration) > 5:  # More than 5 seconds difference
            # Look for a closer match among all available texts
            all_texts = []
            for texts in self.SAMPLE_TEXTS.values():
                all_texts.extend(texts)
            
            # Find text with closest reading time
            closest_text = prompt
            closest_diff = abs(estimated_time - duration)
            
            for text in all_texts:
                text_est_time = self.estimate_reading_time(text)
                diff = abs(text_est_time - duration)
                
                if diff < closest_diff:
                    closest_diff = diff
                    closest_text = text
            
            prompt = closest_text
        
        return prompt

    def get_prompt_with_duration_info(self, duration):
        """
        Get a text prompt with information about estimated reading time
        :param duration: Expected recording duration in seconds
        :return: Dictionary with prompt text and duration info
        """
        prompt = self.get_prompt_text(duration)
        estimated_time = self.estimate_reading_time(prompt)
        
        return {
            'text': prompt,
            'estimated_reading_time': estimated_time,
            'requested_duration': duration,
            'time_difference': abs(estimated_time - duration)
        }


# Example usage
if __name__ == "__main__":
    prompter = TextPrompter()
    
    # Test with different durations
    for duration in [5, 10, 15, 20, 30]:
        result = prompter.get_prompt_with_duration_info(duration)
        print(f"\nDuration: {duration}s | Estimated: {result['estimated_reading_time']}s")
        print(f"Prompt: {result['text'][:100]}{'...' if len(result['text']) > 100 else ''}")