from event.qa_single_generator import QASingleGenerator

qa_single_generator = QASingleGenerator()
qa_single_generator.load_data_from_path('output/fenghaoran/')
res = qa_single_generator.generate_event_questions(3,'2025-04-01')
# res = qa_single_generator.generate_persona_based_sms_questions('2025-03')
print(res)
#qa_single_generator.generate_yearly_single_hop_qa(2025,'single_hop_qa.json')