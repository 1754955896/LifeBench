from event.persona_address_generator import PersonaAddressGenerator
generator = PersonaAddressGenerator()

# 使用示例画像数据路径
example_persona_path = "data/xujing/persona.json"
example_output_path = "output/xujing"

generator.generate_and_save_address_data(example_persona_path, example_output_path)