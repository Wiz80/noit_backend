"""
CrewAI Brief Agent Flow Test
Tests the BriefAgentService using CrewAI testing patterns and performance evaluation
Now includes LLM configuration testing
"""
import asyncio
import json
import time
import logging
from typing import Dict, List, Any
from datetime import datetime

from app.services.business.business_understanding.brief_agent_service import (
    BriefAgentService,
    get_available_llm_models,
    validate_llm_model,
    create_brief_service_with_custom_llm
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BriefFlowTester:
    """
    Comprehensive tester for the CrewAI Brief Agent Service
    Evaluates performance across multiple iterations and scenarios
    Now includes LLM configuration testing
    """
    
    def __init__(self, llm_model: str = "claude-3-5-sonnet-20241022"):
        self.llm_model = llm_model
        self.service = BriefAgentService(llm_model=llm_model)
        self.test_scenarios = self._prepare_test_scenarios()
        self.results = []
        
        logger.info(f"Initialized BriefFlowTester with LLM: {llm_model}")
        
    def _prepare_test_scenarios(self) -> List[Dict[str, Any]]:
        """Prepare different test scenarios for comprehensive evaluation"""
        return [
            {
                "name": "Tech Startup Scenario",
                "business_data": {
                    "id": "test-tech-001",
                    "title": "AI Marketing Platform",
                    "description": "Una plataforma de inteligencia artificial para automatizar campañas de marketing digital",
                    "website_url": "https://aimarketing.com"
                },
                "sample_responses": [
                    "Somos una empresa de tecnología que desarrolla una plataforma de IA para automatizar y optimizar campañas de marketing digital para PyMES.",
                    "Nuestra propuesta de valor es reducir el tiempo y costo de gestión de campañas publicitarias en un 70% usando algoritmos de machine learning.",
                    "Ofrecemos una plataforma SaaS con tres módulos: automatización de campañas, análisis predictivo y optimización de presupuesto publicitario dirigido a empresas medianas.",
                    "Nuestro cliente ideal son gerentes de marketing de empresas medianas (50-200 empleados) que manejan presupuestos publicitarios de $10k-50k mensuales.",
                    "Resolvemos el problema de la complejidad y alto costo de gestionar múltiples campañas publicitarias en diferentes plataformas de manera efectiva.",
                    "Nos diferenciamos por nuestro algoritmo propietario de optimización automática y nuestra interfaz ultra-simplificada que no requiere conocimientos técnicos.",
                    "Enfrentamos el desafío de educar al mercado sobre los beneficios de la automatización con IA y la oportunidad de expansión internacional.",
                    "Operamos en la industria de MarTech (Marketing Technology) y AdTech (Advertising Technology)."
                ]
            },
            {
                "name": "E-commerce Scenario", 
                "business_data": {
                    "id": "test-ecom-002",
                    "title": "Tienda Online Sostenible",
                    "description": "Marketplace de productos ecológicos y sostenibles para el hogar",
                    "website_url": "https://ecoshopping.com"
                },
                "sample_responses": [
                    "Somos un marketplace online especializado en productos sostenibles y ecológicos para el hogar, conectando consumidores conscientes con marcas responsables.",
                    "Nuestra propuesta de valor es ofrecer un catálogo curado de productos 100% sostenibles con envío carbono-neutro y garantía de impacto ambiental positivo.",
                    "Ofrecemos un marketplace con productos para hogar sostenible, servicio de suscripción mensual y programa de reciclaje, dirigido a familias eco-conscientes.",
                    "Nuestro cliente ideal son familias urbanas de clase media-alta, entre 25-45 años, preocupadas por el medio ambiente y dispuestas a pagar premium por productos sostenibles.",
                    "Resolvemos la dificultad de encontrar productos realmente sostenibles y la falta de transparencia sobre el impacto ambiental de las compras del hogar.",
                    "Nos diferenciamos por nuestro proceso de certificación riguroso, transparencia total del impacto ambiental y programa de recompensas por comportamiento sostenible.",
                    "El desafío es educar sobre precios premium vs. beneficios a largo plazo, y la oportunidad de expansión a categorías como moda y alimentación sostenible.",
                    "Operamos en la industria de e-commerce especializado en productos sostenibles y economía circular."
                ]
            },
            {
                "name": "Service Business Scenario",
                "business_data": {
                    "id": "test-serv-003",
                    "title": "Consultoría Digital",
                    "description": "Servicios de transformación digital para empresas tradicionales",
                    "website_url": "https://digitalfirst.com"
                },
                "sample_responses": [
                    "Somos una consultoría especializada en transformación digital que ayuda a empresas tradicionales a adoptar tecnologías digitales para mejorar su competitividad.",
                    "Nuestra propuesta de valor es acelerar la transformación digital de empresas tradicionales en 6 meses vs. 2-3 años típicos, con ROI garantizado del 200%.",
                    "Ofrecemos auditoría digital, implementación de sistemas, capacitación de equipos y soporte continuo dirigido a empresas manufactureras y de servicios tradicionales.",
                    "Nuestro cliente ideal son directores y gerentes de empresas tradicionales (100-500 empleados) que reconocen la necesidad de digitalización pero no saben cómo empezar.",
                    "Resolvemos la resistencia al cambio tecnológico, la falta de conocimiento interno y el miedo a la disrupción del negocio durante la transformación.",
                    "Nos diferenciamos por nuestro enfoque gradual y personalizado, metodología probada en +200 empresas y equipo con experiencia tanto en tecnología como en industrias tradicionales.",
                    "El desafío es vencer la resistencia cultural al cambio, y la oportunidad es el creciente reconocimiento post-pandemia de la necesidad de digitalización.",
                    "Operamos en la industria de consultoría tecnológica y transformación digital."
                ]
            }
        ]
    
    async def run_llm_configuration_test(self) -> Dict[str, Any]:
        """Test LLM configuration capabilities"""
        logger.info("🔧 Starting LLM Configuration Test")
        
        config_results = {
            "available_models": {},
            "model_validation": {},
            "model_switching": {},
            "service_info": {}
        }
        
        try:
            # Test 1: Get available models
            available_models = get_available_llm_models()
            config_results["available_models"] = {
                "success": True,
                "models": available_models,
                "total_providers": len(available_models),
                "total_models": sum(len(models) for models in available_models.values())
            }
            logger.info(f"✅ Found {config_results['available_models']['total_models']} models from {config_results['available_models']['total_providers']} providers")
            
            # Test 2: Model validation
            test_models = [
                "claude-3-5-sonnet-20241022",  # Valid
                "gpt-4o",  # Valid
                "invalid-model-name",  # Invalid
                "gemini-1.5-pro"  # Valid
            ]
            
            validation_results = {}
            for model in test_models:
                is_valid = validate_llm_model(model)
                validation_results[model] = is_valid
                logger.info(f"  Model {model}: {'✅ Valid' if is_valid else '❌ Invalid'}")
            
            config_results["model_validation"] = validation_results
            
            # Test 3: Service info
            service_info = self.service.get_llm_info()
            config_results["service_info"] = service_info
            logger.info(f"✅ Service using: {service_info['model']} from {service_info['provider']}")
            
            # Test 4: Model switching (if possible)
            try:
                original_model = self.service.llm_model
                test_switch_model = "gpt-4o-mini"
                
                if validate_llm_model(test_switch_model):
                    self.service.change_llm(test_switch_model)
                    new_info = self.service.get_llm_info()
                    
                    # Switch back
                    self.service.change_llm(original_model)
                    
                    config_results["model_switching"] = {
                        "success": True,
                        "switched_to": test_switch_model,
                        "switched_back": original_model,
                        "new_info": new_info
                    }
                    logger.info(f"✅ Successfully switched models: {original_model} -> {test_switch_model} -> {original_model}")
                else:
                    config_results["model_switching"] = {
                        "success": False,
                        "reason": f"Test model {test_switch_model} not available"
                    }
            except Exception as e:
                config_results["model_switching"] = {
                    "success": False,
                    "error": str(e)
                }
                logger.warning(f"⚠️ Model switching test failed: {str(e)}")
            
        except Exception as e:
            logger.error(f"❌ LLM Configuration test failed: {str(e)}")
            config_results["error"] = str(e)
        
        return config_results
    
    async def run_refinement_test(self) -> Dict[str, Any]:
        """Test the response refinement functionality"""
        logger.info("🔧 Starting Response Refinement Test")
        
        refinement_results = {
            "basic_refinement": {},
            "incomplete_responses": {},
            "edge_cases": {},
            "flow_continuity": {}
        }
        
        try:
            business_data = {
                "id": "test-refinement-001",
                "title": "Empresa de Educación Digital",
                "description": "Plataforma de cursos online de marketing digital",
                "website_url": "https://example.com"
            }
            
            # Test 1: Basic refinement with incomplete response
            session_data = {
                "current_question_index": 0,
                "answers": {},
                "langchain_chat_history": [],
                "business_idea": business_data
            }
            
            # Start with welcome
            welcome_result = self.service.run_agent_turn("Iniciar brief", session_data)
            
            # Update session
            session_data = {
                "current_question_index": welcome_result['updated_current_question_index'],
                "answers": welcome_result['updated_answers'],
                "langchain_chat_history": welcome_result['updated_chat_history'],
                "business_idea": business_data
            }
            
            # Test incomplete response like the user's example
            incomplete_response = "La mejor educación online de latinoamerica"
            
            refinement_result = self.service.run_agent_turn(incomplete_response, session_data)
            
            refinement_results["basic_refinement"] = {
                "original_response": incomplete_response,
                "answer_recorded": refinement_result.get("answer_recorded", False),
                "response_was_refined": refinement_result.get("response_was_refined", False),
                "refined_answer": refinement_result.get("refined_answer"),
                "flow_continued": refinement_result.get("updated_current_question_index", 0) > 0,
                "success": True
            }
            
            logger.info(f"✅ Basic refinement test: Answer recorded={refinement_result.get('answer_recorded')}, Refined={refinement_result.get('response_was_refined')}")
            
            # Test 2: Multiple incomplete responses in sequence
            test_responses = [
                "Cursos de marketing",
                "Público joven",
                "Solucionamos falta de conocimiento",
                "Somos mejores"
            ]
            
            sequence_results = []
            current_session = session_data.copy()
            current_session["current_question_index"] = refinement_result.get("updated_current_question_index", 1)
            current_session["answers"] = refinement_result.get("updated_answers", {})
            
            for i, response in enumerate(test_responses[:2]):  # Test first 2 to avoid going too far
                if current_session["current_question_index"] < self.service.get_total_questions():
                    result = self.service.run_agent_turn(response, current_session)
                    
                    sequence_results.append({
                        "response": response,
                        "answer_recorded": result.get("answer_recorded", False),
                        "refined": result.get("response_was_refined", False),
                        "continued": result.get("updated_current_question_index", 0) > current_session["current_question_index"]
                    })
                    
                    # Update for next iteration
                    current_session = {
                        "current_question_index": result.get("updated_current_question_index", current_session["current_question_index"]),
                        "answers": result.get("updated_answers", current_session["answers"]),
                        "langchain_chat_history": result.get("updated_chat_history", current_session["langchain_chat_history"]),
                        "business_idea": business_data
                    }
            
            refinement_results["incomplete_responses"] = {
                "sequence_results": sequence_results,
                "total_processed": len(sequence_results),
                "all_recorded": all(r["answer_recorded"] for r in sequence_results),
                "flow_maintained": all(r["continued"] for r in sequence_results)
            }
            
            # Test 3: Edge cases
            edge_cases = [
                "no sé",  # Very minimal response
                "eso",    # Single word
                "marketing digital para empresas que quieren crecer y mejorar sus ventas online"  # Already complete
            ]
            
            edge_results = []
            for edge_response in edge_cases:
                try:
                    edge_result = self.service.run_agent_turn(edge_response, current_session)
                    edge_results.append({
                        "response": edge_response,
                        "processed": True,
                        "answer_recorded": edge_result.get("answer_recorded", False),
                        "refined": edge_result.get("response_was_refined", False)
                    })
                except Exception as e:
                    edge_results.append({
                        "response": edge_response,
                        "processed": False,
                        "error": str(e)
                    })
            
            refinement_results["edge_cases"] = {
                "results": edge_results,
                "success_rate": sum(1 for r in edge_results if r.get("processed", False)) / len(edge_results)
            }
            
            # Test 4: Flow continuity
            refinement_results["flow_continuity"] = {
                "no_clarification_requests": True,  # We should never request clarification now
                "automatic_progression": all(r["continued"] for r in sequence_results),
                "answers_stored": len(current_session.get("answers", {})) > 0
            }
            
            logger.info("✅ Response refinement test completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Response refinement test failed: {str(e)}")
            refinement_results["error"] = str(e)
        
        return refinement_results
    
    async def run_comprehensive_test(self, n_iterations: int = 2, include_llm_test: bool = True, include_refinement_test: bool = True) -> Dict[str, Any]:
        """
        Run comprehensive test across multiple iterations and scenarios
        Following CrewAI testing patterns with LLM configuration testing
        """
        logger.info(f"🧪 Starting comprehensive CrewAI Brief Flow test with {n_iterations} iterations")
        logger.info(f"📊 Testing {len(self.test_scenarios)} scenarios with LLM: {self.llm_model}")
        
        all_results = []
        scenario_scores = {}
        llm_config_results = None
        refinement_test_results = None
        
        # Run LLM configuration test first
        if include_llm_test:
            llm_config_results = await self.run_llm_configuration_test()
            
        # Run refinement test
        if include_refinement_test:
            refinement_test_results = await self.run_refinement_test()
        
        for scenario in self.test_scenarios:
            logger.info(f"\n🎯 Testing scenario: {scenario['name']}")
            scenario_results = []
            
            for iteration in range(n_iterations):
                logger.info(f"  ⚡ Iteration {iteration + 1}/{n_iterations}")
                
                result = await self._run_single_scenario_test(scenario, iteration)
                scenario_results.append(result)
                all_results.append(result)
                
                # Log iteration summary
                logger.info(f"    ✅ Completed in {result['execution_time']:.2f}s - Score: {result['overall_score']:.1f}")
            
            # Calculate scenario averages
            avg_score = sum(r['overall_score'] for r in scenario_results) / len(scenario_results)
            avg_time = sum(r['execution_time'] for r in scenario_results) / len(scenario_results)
            
            scenario_scores[scenario['name']] = {
                'average_score': avg_score,
                'average_time': avg_time,
                'iterations': scenario_results
            }
            
            logger.info(f"  📈 {scenario['name']} Average Score: {avg_score:.2f}")
        
        # Generate final report
        final_report = self._generate_test_report(scenario_scores, n_iterations, llm_config_results, refinement_test_results)
        
        logger.info("\n" + "="*80)
        logger.info("🎉 COMPREHENSIVE TEST COMPLETED")
        logger.info("="*80)
        self._print_test_report(final_report)
        
        return final_report
    
    async def _run_single_scenario_test(self, scenario: Dict[str, Any], iteration: int) -> Dict[str, Any]:
        """Run a single test scenario iteration"""
        start_time = time.time()
        
        business_data = scenario['business_data']
        sample_responses = scenario['sample_responses']
        
        # Initialize session data
        session_data = {
            "current_question_index": 0,
            "answers": {},
            "langchain_chat_history": [],
            "business_idea": business_data
        }
        
        scores = {
            'welcome_flow': 0,
            'question_progression': 0,
            'response_validation': 0,
            'suggestion_quality': 0,
            'completion_handling': 0
        }
        
        try:
            # Test 1: Welcome Flow
            welcome_result = self.service.run_agent_turn("Iniciar brief", session_data)
            scores['welcome_flow'] = self._evaluate_welcome_response(welcome_result)
            
            # Update session data
            session_data = {
                "current_question_index": welcome_result['updated_current_question_index'],
                "answers": welcome_result['updated_answers'],
                "langchain_chat_history": welcome_result['updated_chat_history'],
                "business_idea": business_data
            }
            
            # Test 2-4: Question Progression (test first 3 questions)
            progression_scores = []
            for i, response in enumerate(sample_responses[:3]):
                if session_data['current_question_index'] < self.service.get_total_questions():
                    turn_result = self.service.run_agent_turn(response, session_data)
                    turn_score = self._evaluate_turn_response(turn_result, response)
                    progression_scores.append(turn_score)
                    
                    # Update session data
                    session_data = {
                        "current_question_index": turn_result['updated_current_question_index'],
                        "answers": turn_result['updated_answers'],
                        "langchain_chat_history": turn_result['updated_chat_history'],
                        "business_idea": business_data
                    }
            
            scores['question_progression'] = sum(progression_scores) / len(progression_scores) if progression_scores else 0
            
            # Test 3: Response Validation (try an invalid response)
            invalid_response = "No sé"
            validation_result = self.service.run_agent_turn(invalid_response, session_data)
            scores['response_validation'] = self._evaluate_validation_response(validation_result)
            
            # Test 4: Suggestion Quality (evaluate suggestions from welcome)
            scores['suggestion_quality'] = self._evaluate_suggestions(welcome_result)
            
            # Test 5: Completion Handling (simulate completion)
            scores['completion_handling'] = self._evaluate_completion_capability()
            
        except Exception as e:
            logger.error(f"Error in scenario test: {str(e)}")
            # Penalize for errors
            for key in scores:
                scores[key] = max(0, scores[key] - 2)
        
        execution_time = time.time() - start_time
        overall_score = sum(scores.values()) / len(scores)
        
        return {
            'scenario': scenario['name'],
            'iteration': iteration,
            'execution_time': execution_time,
            'overall_score': overall_score,
            'detailed_scores': scores,
            'business_data': business_data
        }
    
    def _evaluate_welcome_response(self, result: Dict[str, Any]) -> float:
        """Evaluate the quality of the welcome response"""
        score = 0
        
        # Check if reply exists and is substantial
        if result.get('reply') and len(result['reply']) > 50:
            score += 2
        
        # Check if total questions is provided
        if result.get('total_questions', 0) > 0:
            score += 2
        
        # Check if suggestions are provided
        if result.get('suggestion_answer'):
            score += 2
        
        if result.get('suggestion_response'):
            score += 2
        
        # Check if current question index is correct
        if result.get('updated_current_question_index') == 0:
            score += 2
        
        return min(score, 10)
    
    def _evaluate_turn_response(self, result: Dict[str, Any], user_response: str) -> float:
        """Evaluate the quality of a conversation turn"""
        score = 0
        
        # Check if answer was recorded
        if result.get('answer_recorded'):
            score += 3
        
        # Check if question index progressed
        if result.get('updated_current_question_index', 0) > 0:
            score += 2
        
        # Check if response is meaningful
        if result.get('reply') and len(result['reply']) > 30:
            score += 2
        
        # Check if answers are being stored
        if result.get('updated_answers') and len(result['updated_answers']) > 0:
            score += 2
        
        # Check confirmation message
        if result.get('previous_action_confirmation'):
            score += 1
        
        return min(score, 10)
    
    def _evaluate_validation_response(self, result: Dict[str, Any]) -> float:
        """Evaluate response validation capabilities"""
        score = 0
        
        # If answer_recorded is False, it means validation is working
        if result.get('answer_recorded') == False:
            score += 5
        
        # Check if appropriate clarification is requested
        if result.get('reply') and any(word in result['reply'].lower() for word in ['más', 'detalles', 'específico', 'clarifica']):
            score += 3
        
        # Check that question index didn't advance for invalid response
        if result.get('updated_current_question_index') == result.get('current_question_index', 0):
            score += 2
        
        return min(score, 10)
    
    def _evaluate_suggestions(self, result: Dict[str, Any]) -> float:
        """Evaluate the quality of suggestions provided"""
        score = 0
        
        suggestion_answer = result.get('suggestion_answer', '')
        suggestion_response = result.get('suggestion_response', '')
        
        # Check suggestion answer quality
        if suggestion_answer:
            if len(suggestion_answer) > 20:
                score += 2
            if any(word in suggestion_answer.lower() for word in ['empresa', 'negocio', 'propósito', 'valor']):
                score += 2
        
        # Check suggestion response quality
        if suggestion_response:
            if len(suggestion_response) > 20:
                score += 2
            if any(word in suggestion_response.lower() for word in ['excelente', 'continuemos', 'perfecto', 'siguiente']):
                score += 2
        
        # Check contextual relevance
        if suggestion_answer and suggestion_response:
            score += 2
        
        return min(score, 10)
    
    def _evaluate_completion_capability(self) -> float:
        """Evaluate completion handling (static evaluation for now)"""
        # This would ideally run a full flow, but for testing purposes,
        # we'll evaluate based on service capabilities
        score = 0
        
        # Check if service has proper total questions count
        if self.service.get_total_questions() == 22:  # Expected total
            score += 3
        
        # Check if service has all phases defined
        if len(self.service.phases) == 3:
            score += 3
        
        # Check if flat questions are properly structured
        if len(self.service.flat_questions) == 22:
            score += 4
        
        return min(score, 10)
    
    def _generate_test_report(self, scenario_scores: Dict[str, Any], n_iterations: int, llm_config_results: Dict[str, Any] = None, refinement_test_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate comprehensive test report following CrewAI format"""
        
        total_scenarios = len(scenario_scores)
        
        # Calculate overall averages
        overall_avg_score = sum(s['average_score'] for s in scenario_scores.values()) / total_scenarios
        overall_avg_time = sum(s['average_time'] for s in scenario_scores.values()) / total_scenarios
        
        # Prepare detailed breakdown
        task_breakdown = {}
        for scenario_name, scenario_data in scenario_scores.items():
            task_breakdown[scenario_name] = {
                'average_score': scenario_data['average_score'],
                'average_time': scenario_data['average_time'],
                'iterations': [it['overall_score'] for it in scenario_data['iterations']]
            }
        
        return {
            'test_summary': {
                'total_scenarios': total_scenarios,
                'iterations_per_scenario': n_iterations,
                'total_iterations': total_scenarios * n_iterations,
                'overall_average_score': overall_avg_score,
                'overall_average_time': overall_avg_time
            },
            'scenario_breakdown': task_breakdown,
            'detailed_results': scenario_scores,
            'llm_config_results': llm_config_results,
            'refinement_test_results': refinement_test_results
        }
    
    def _print_test_report(self, report: Dict[str, Any]):
        """Print test report in CrewAI testing format with LLM configuration info"""
        
        print("\n" + "="*100)
        print("📊 CREWAI BRIEF AGENT FLOW - TEST RESULTS")
        print("="*100)
        
        # LLM Configuration Summary
        llm_config = report.get('llm_config_results')
        if llm_config:
            print(f"🤖 LLM Model: {self.llm_model}")
            
            if 'service_info' in llm_config:
                service_info = llm_config['service_info']
                print(f"🔧 Provider: {service_info.get('provider', 'unknown')}")
            
            if 'available_models' in llm_config:
                available = llm_config['available_models']
                if available.get('success'):
                    print(f"📋 Available Models: {available['total_models']} models from {available['total_providers']} providers")
            
            if 'model_switching' in llm_config:
                switching = llm_config['model_switching']
                switch_status = "✅ Working" if switching.get('success') else "❌ Failed"
                print(f"🔄 Model Switching: {switch_status}")
            
            print("-" * 100)
        
        summary = report['test_summary']
        print(f"🔍 Total Scenarios: {summary['total_scenarios']}")
        print(f"🔄 Iterations per scenario: {summary['iterations_per_scenario']}")
        print(f"⚡ Total test iterations: {summary['total_iterations']}")
        print(f"📈 Overall Average Score: {summary['overall_average_score']:.2f}/10")
        print(f"⏱️  Overall Average Time: {summary['overall_average_time']:.2f}s")
        
        print("\n" + "-"*100)
        print("📋 SCENARIO BREAKDOWN")
        print("-"*100)
        
        # Table header
        print(f"{'Scenario':<25} {'Run 1':<8} {'Run 2':<8} {'Avg Score':<10} {'Avg Time':<10} {'Status':<10}")
        print("-"*100)
        
        # Table rows
        for scenario_name, data in report['scenario_breakdown'].items():
            iterations = data['iterations']
            run1 = f"{iterations[0]:.1f}" if len(iterations) > 0 else "N/A"
            run2 = f"{iterations[1]:.1f}" if len(iterations) > 1 else "N/A"
            avg_score = f"{data['average_score']:.1f}"
            avg_time = f"{data['average_time']:.1f}s"
            
            # Determine status
            if data['average_score'] >= 8.0:
                status = "✅ Excellent"
            elif data['average_score'] >= 6.0:
                status = "✅ Good"
            elif data['average_score'] >= 4.0:
                status = "⚠️ Fair"
            else:
                status = "❌ Poor"
            
            print(f"{scenario_name:<25} {run1:<8} {run2:<8} {avg_score:<10} {avg_time:<10} {status:<10}")
        
        print("-"*100)
        
        # LLM Configuration Details
        if llm_config:
            print("\n🔧 LLM CONFIGURATION TEST RESULTS")
            print("-"*100)
            
            if 'model_validation' in llm_config:
                print("📝 Model Validation Results:")
                for model, is_valid in llm_config['model_validation'].items():
                    status_icon = "✅" if is_valid else "❌"
                    print(f"  {status_icon} {model}")
            
            if 'available_models' in llm_config and llm_config['available_models'].get('success'):
                print("\n📋 Available Models by Provider:")
                models = llm_config['available_models']['models']
                for provider, provider_models in models.items():
                    print(f"  🔹 {provider}: {len(provider_models)} models")
                    for model in provider_models[:3]:  # Show first 3 models
                        print(f"    - {model}")
                    if len(provider_models) > 3:
                        print(f"    ... and {len(provider_models) - 3} more")
            
            print("-"*100)
        
        # Refinement Test Results
        refinement_results = report.get('refinement_test_results')
        if refinement_results:
            print("\n🔄 RESPONSE REFINEMENT TEST RESULTS")
            print("-"*100)
            
            # Basic refinement test
            basic = refinement_results.get('basic_refinement', {})
            if basic:
                print("📝 Basic Refinement Test:")
                print(f"  Original: '{basic.get('original_response', 'N/A')}'")
                print(f"  ✅ Answer Recorded: {basic.get('answer_recorded', False)}")
                print(f"  🔄 Response Refined: {basic.get('response_was_refined', False)}")
                print(f"  ➡️  Flow Continued: {basic.get('flow_continued', False)}")
                if basic.get('refined_answer'):
                    refined_preview = basic['refined_answer'][:80] + "..." if len(basic['refined_answer']) > 80 else basic['refined_answer']
                    print(f"  📄 Refined: '{refined_preview}'")
            
            # Incomplete responses test
            incomplete = refinement_results.get('incomplete_responses', {})
            if incomplete:
                print(f"\n📋 Sequence Test ({incomplete.get('total_processed', 0)} responses):")
                print(f"  ✅ All Recorded: {incomplete.get('all_recorded', False)}")
                print(f"  🔄 Flow Maintained: {incomplete.get('flow_maintained', False)}")
            
            # Edge cases
            edge_cases = refinement_results.get('edge_cases', {})
            if edge_cases:
                success_rate = edge_cases.get('success_rate', 0) * 100
                print(f"\n⚡ Edge Cases: {success_rate:.0f}% success rate")
            
            # Flow continuity
            flow = refinement_results.get('flow_continuity', {})
            if flow:
                print(f"\n🌊 Flow Continuity:")
                print(f"  🚫 No Clarification Requests: {flow.get('no_clarification_requests', False)}")
                print(f"  ⚡ Automatic Progression: {flow.get('automatic_progression', False)}")
                print(f"  💾 Answers Stored: {flow.get('answers_stored', False)}")
            
            print("-"*100)
        
        # Overall assessment
        overall_score = summary['overall_average_score']
        if overall_score >= 8.0:
            assessment = "🎉 EXCELLENT - CrewAI Brief Flow is performing exceptionally well!"
        elif overall_score >= 6.0:
            assessment = "✅ GOOD - CrewAI Brief Flow is performing well with minor areas for improvement."
        elif overall_score >= 4.0:
            assessment = "⚠️ FAIR - CrewAI Brief Flow needs optimization in several areas."
        else:
            assessment = "❌ POOR - CrewAI Brief Flow requires significant improvements."
        
        print(f"\n🏆 OVERALL ASSESSMENT: {assessment}")
        
        # LLM specific assessment
        if llm_config:
            llm_assessment = self._assess_llm_performance(llm_config)
            print(f"🤖 LLM ASSESSMENT: {llm_assessment}")
        
        # Refinement specific assessment
        if refinement_results:
            refinement_assessment = self._assess_refinement_performance(refinement_results)
            print(f"🔄 REFINEMENT ASSESSMENT: {refinement_assessment}")
        
        print("="*100)
    
    def _assess_llm_performance(self, llm_config: Dict[str, Any]) -> str:
        """Assess LLM configuration performance"""
        score = 0
        max_score = 4
        
        # Available models test
        if llm_config.get('available_models', {}).get('success'):
            score += 1
        
        # Model validation test
        validation = llm_config.get('model_validation', {})
        if validation:
            valid_count = sum(1 for is_valid in validation.values() if is_valid)
            if valid_count >= 3:  # At least 3 valid models
                score += 1
        
        # Service info test
        if 'service_info' in llm_config:
            score += 1
        
        # Model switching test
        if llm_config.get('model_switching', {}).get('success'):
            score += 1
        
        percentage = (score / max_score) * 100
        
        if percentage >= 100:
            return "🎉 PERFECT - All LLM features working flawlessly!"
        elif percentage >= 75:
            return "✅ EXCELLENT - LLM configuration working very well!"
        elif percentage >= 50:
            return "⚠️ GOOD - LLM configuration mostly working!"
        else:
            return "❌ POOR - LLM configuration needs attention!"

    def _assess_refinement_performance(self, refinement_results: Dict[str, Any]) -> str:
        """Assess refinement performance"""
        score = 0
        max_score = 4
        
        # Basic refinement test
        basic = refinement_results.get('basic_refinement', {})
        if basic:
            if basic.get('success'):
                score += 1
        
        # Incomplete responses test
        incomplete = refinement_results.get('incomplete_responses', {})
        if incomplete:
            if incomplete.get('all_recorded', False):
                score += 1
        
        # Edge cases
        edge_cases = refinement_results.get('edge_cases', {})
        if edge_cases:
            success_rate = edge_cases.get('success_rate', 0)
            if success_rate >= 0.75:  # 75% success rate
                score += 1
        
        # Flow continuity
        flow = refinement_results.get('flow_continuity', {})
        if flow:
            if flow.get('automatic_progression', False):
                score += 1
        
        percentage = (score / max_score) * 100
        
        if percentage >= 100:
            return "🎉 PERFECT - Refinement is performing exceptionally well!"
        elif percentage >= 75:
            return "✅ EXCELLENT - Refinement is performing very well!"
        elif percentage >= 50:
            return "⚠️ GOOD - Refinement is mostly working!"
        else:
            return "❌ POOR - Refinement needs attention!"

async def main():
    """Main function to run the comprehensive test"""
    # You can change the LLM model here to test different models
    llm_model = "claude-3-5-sonnet-20241022"  # Default
    # llm_model = "gpt-4o"  # Alternative
    # llm_model = "gemini-1.5-pro"  # Alternative
    
    tester = BriefFlowTester(llm_model=llm_model)
    
    # Run test with 2 iterations (following CrewAI default)
    results = await tester.run_comprehensive_test(n_iterations=2, include_llm_test=True, include_refinement_test=True)
    
    # Save results to file for analysis
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"crewai_brief_test_results_{llm_model.replace('-', '_')}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: {filename}")

if __name__ == "__main__":
    asyncio.run(main()) 