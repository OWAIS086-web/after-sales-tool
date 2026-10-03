# Enhanced PDF Report Generation Functions
# This module contains the enhanced report generation logic with Problem Statement, 
# Fact-based Analysis, Assumptions, and Objective Conclusions

def generate_enhanced_pdf_report(source, report_type, period, analytics_data, conversions_data, user_company, token_stats=None):
    """Generate enhanced PDF report with comprehensive sections - all sections always included
    
    Args:
        source: Data source (pakwheels, whatsapp, reddit)
        report_type: Type of report (summary, detailed)
        period: Time period for report
        analytics_data: Analytics statistics
        conversions_data: Chart/conversion data
        user_company: Company name
        token_stats: Optional token usage and cost statistics
    """
    from datetime import datetime
    from io import BytesIO
    import os
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Define custom styles with black and red colors
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#000000'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#CC0000'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#000000'),
        spaceAfter=8,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        alignment=TA_JUSTIFY
    )
    
    # Add logo at the top center - smaller size to fit on all pages
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'black-logo.png')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=1.5*inch, height=0.45*inch)
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 0.08*inch))
        except Exception as e:
            # If logo fails to load, continue without it
            pass
    
    # Title
    elements.append(Paragraph(f'Analytics Report - {source.upper()}', title_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Report Info
    report_info = [
        ['Report Type:', report_type.capitalize()],
        ['Time Period:', period],
        ['Company:', user_company],
        ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    ]
    
    info_table = Table(report_info, colWidths=[1.5*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 0.15*inch))
    
    # Extract data for all sources
    if source == 'pakwheels':
        total_posts = analytics_data.get('totalPosts', 0)
        unique_authors = analytics_data.get('activeUsers', 0)
        unique_topics = analytics_data.get('newUsers', 0)
        complaints = analytics_data.get('complaints', 0)
        sentiment_labels = conversions_data.get('labels', ['Positive Posts', 'Negative Posts', 'Neutral Posts'])
        sentiment_values = conversions_data.get('data', [0, 0, 0])
        
    elif source == 'whatsapp':
        total_posts = analytics_data.get('totalPosts', 0)
        unique_authors = analytics_data.get('activeUsers', 0)
        unique_topics = analytics_data.get('newUsers', 0)
        complaints = analytics_data.get('complaints', 0)
        message_labels = conversions_data.get('labels', ['Queries', 'Complaints', 'Support', 'General'])
        message_values = conversions_data.get('data', [0, 0, 0, 0])
        
    else:  # reddit
        total_posts = analytics_data.get('totalPosts', 0)
        unique_authors = analytics_data.get('activeUsers', 0)
        unique_topics = analytics_data.get('newUsers', 0)
        complaints = analytics_data.get('complaints', 0)
        sentiment_labels = conversions_data.get('labels', ['Positive Posts', 'Negative Posts', 'Neutral Posts'])
        sentiment_values = conversions_data.get('data', [0, 0, 0])
    
    # PROBLEM STATEMENT
    elements.append(Paragraph('Problem Statement', heading_style))
    
    if source == 'pakwheels':
        problem_text = f"""
        This report addresses the need to understand customer sentiment, engagement patterns, and complaint trends on PakWheels. 
        The organization requires comprehensive insights into {total_posts} posts from {unique_authors} unique authors to identify 
        areas of concern, measure brand perception, and develop targeted improvement strategies. With {complaints} complaints identified, 
        there is a critical need to analyze root causes and implement corrective actions.
        """
    elif source == 'whatsapp':
        problem_text = f"""
        This report analyzes WhatsApp communication to understand customer satisfaction, identify common issues, and optimize support processes. 
        The organization needs to evaluate {total_posts} messages from {unique_authors} customers to address {complaints} complaints, 
        respond to customer queries efficiently, and improve overall customer experience. Understanding communication patterns is essential 
        for resource allocation and service improvement.
        """
    else:
        problem_text = f"""
        This report examines Reddit discussions to monitor brand perception, identify customer concerns, and track community engagement. 
        With {total_posts} posts from {unique_authors} authors, the organization needs to understand sentiment distribution and address 
        {complaints} complaints to maintain positive brand reputation and community relationships.
        """
    
    elements.append(Paragraph(problem_text, normal_style))
    elements.append(Spacer(1, 0.12*inch))
    
    # KEY METRICS
    elements.append(Paragraph('Key Metrics & Data Summary', heading_style))
    
    if source == 'pakwheels':
        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Posts', str(total_posts), '✓'],
            ['Unique Authors', str(unique_authors), '✓'],
            ['Unique Topics', str(unique_topics), '✓'],
            ['Total Complaints', str(complaints), '⚠' if complaints > 0 else '✓'],
            [sentiment_labels[0] if len(sentiment_labels) > 0 else 'Positive', str(sentiment_values[0] if len(sentiment_values) > 0 else 0), '↑'],
            [sentiment_labels[1] if len(sentiment_labels) > 1 else 'Negative', str(sentiment_values[1] if len(sentiment_values) > 1 else 0), '↓'],
            [sentiment_labels[2] if len(sentiment_labels) > 2 else 'Neutral', str(sentiment_values[2] if len(sentiment_values) > 2 else 0), '→']
        ]
    elif source == 'whatsapp':
        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Messages', str(total_posts), '✓'],
            ['Unique Customers', str(unique_authors), '✓'],
            ['Total Complaints', str(complaints), '⚠' if complaints > 0 else '✓'],
            [message_labels[0] if len(message_labels) > 0 else 'Queries', str(message_values[0] if len(message_values) > 0 else 0), '✓'],
            [message_labels[1] if len(message_labels) > 1 else 'Complaints', str(message_values[1] if len(message_values) > 1 else 0), '⚠'],
            [message_labels[2] if len(message_labels) > 2 else 'Support', str(message_values[2] if len(message_values) > 2 else 0), '✓'],
            [message_labels[3] if len(message_labels) > 3 else 'General', str(message_values[3] if len(message_values) > 3 else 0), '✓']
        ]
    else:
        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Posts', str(total_posts), '✓'],
            ['Unique Authors', str(unique_authors), '✓'],
            ['Unique Topics', str(unique_topics), '✓'],
            ['Total Complaints', str(complaints), '⚠' if complaints > 0 else '✓'],
            [sentiment_labels[0] if len(sentiment_labels) > 0 else 'Positive', str(sentiment_values[0] if len(sentiment_values) > 0 else 0), '↑'],
            [sentiment_labels[1] if len(sentiment_labels) > 1 else 'Negative', str(sentiment_values[1] if len(sentiment_values) > 1 else 0), '↓'],
            [sentiment_labels[2] if len(sentiment_labels) > 2 else 'Neutral', str(sentiment_values[2] if len(sentiment_values) > 2 else 0), '→']
        ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch, 0.8*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#000000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CC0000')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.1*inch))
    
    # FACT-BASED ANALYSIS
    elements.append(PageBreak())
    elements.append(Paragraph('Fact-Based Analysis', heading_style))
    
    if source == 'pakwheels':
        analysis_text = f"""
        <b>Engagement Metrics:</b> The platform shows {total_posts} posts from {unique_authors} unique authors, indicating an average engagement 
        of {round(total_posts/max(unique_authors, 1), 2)} posts per author. This demonstrates the level of community participation and brand visibility.
        <br/><br/>
        <b>Sentiment Distribution:</b> The sentiment analysis reveals {sentiment_values[0] if len(sentiment_values) > 0 else 0} positive posts ({round((sentiment_values[0]/max(total_posts, 1))*100, 1)}%), 
        {sentiment_values[1] if len(sentiment_values) > 1 else 0} negative posts ({round((sentiment_values[1]/max(total_posts, 1))*100, 1)}%), and {sentiment_values[2] if len(sentiment_values) > 2 else 0} neutral posts ({round((sentiment_values[2]/max(total_posts, 1))*100, 1)}%). 
        This distribution indicates the overall brand perception on the platform.
        <br/><br/>
        <b>Complaint Analysis:</b> {complaints} complaints have been identified, representing {round((complaints/max(total_posts, 1))*100, 2)}% of total posts. 
        These complaints require immediate attention and systematic resolution to improve customer satisfaction.
        <br/><br/>
        <b>Topic Diversity:</b> {unique_topics} unique topics were discussed, indicating diverse customer interests and concerns across multiple product/service categories.
        """
    elif source == 'whatsapp':
        complaint_rate = round((complaints/max(total_posts, 1))*100, 2) if total_posts > 0 else 0
        analysis_text = f"""
        <b>Communication Volume:</b> {total_posts} messages from {unique_authors} unique customers indicate active engagement and customer interest. 
        This represents an average of {round(total_posts/max(unique_authors, 1), 2)} messages per customer.
        <br/><br/>
        <b>Message Type Distribution:</b> The communication breakdown shows {message_values[0] if len(message_values) > 0 else 0} queries, 
        {message_values[1] if len(message_values) > 1 else 0} complaints, {message_values[2] if len(message_values) > 2 else 0} support messages, 
        and {message_values[3] if len(message_values) > 3 else 0} general messages. This distribution helps identify customer needs and support requirements.
        <br/><br/>
        <b>Complaint Rate:</b> The complaint rate of {complaint_rate}% indicates customer satisfaction levels. 
        A lower rate suggests higher satisfaction, while higher rates indicate areas requiring immediate attention.
        <br/><br/>
        <b>Query Volume:</b> {message_values[0] if len(message_values) > 0 else 0} queries demonstrate active customer engagement and interest in products/services. 
        Efficient query resolution is critical for customer retention.
        """
    else:
        analysis_text = f"""
        <b>Community Engagement:</b> {total_posts} posts from {unique_authors} unique authors show active community participation. 
        Average engagement is {round(total_posts/max(unique_authors, 1), 2)} posts per author.
        <br/><br/>
        <b>Sentiment Analysis:</b> {sentiment_values[0] if len(sentiment_values) > 0 else 0} positive posts ({round((sentiment_values[0]/max(total_posts, 1))*100, 1)}%), 
        {sentiment_values[1] if len(sentiment_values) > 1 else 0} negative posts ({round((sentiment_values[1]/max(total_posts, 1))*100, 1)}%), and {sentiment_values[2] if len(sentiment_values) > 2 else 0} neutral posts ({round((sentiment_values[2]/max(total_posts, 1))*100, 1)}%).
        <br/><br/>
        <b>Complaint Tracking:</b> {complaints} complaints identified, representing {round((complaints/max(total_posts, 1))*100, 2)}% of discussions. 
        These require monitoring and response.
        <br/><br/>
        <b>Topic Coverage:</b> {unique_topics} unique topics discussed across the community, showing diverse customer interests.
        """
    
    elements.append(Paragraph(analysis_text, normal_style))
    elements.append(Spacer(1, 0.12*inch))
    
    # ASSUMPTIONS
    elements.append(Paragraph('Assumptions & Methodology', heading_style))
    
    assumptions_text = f"""
    <b>Data Collection:</b> This report is based on data collected from {source.upper()} during the {period} period. 
    All metrics are calculated from verified records in the system.
    <br/><br/>
    <b>Sentiment Classification:</b> Sentiment analysis is performed using automated classification algorithms. 
    Classifications are based on language patterns, keywords, and contextual analysis.
    <br/><br/>
    <b>Complaint Identification:</b> Complaints are identified through keyword matching and sentiment analysis. 
    Some complaints may be missed if they use non-standard language or terminology.
    <br/><br/>
    <b>Data Accuracy:</b> The accuracy of this report depends on the quality and completeness of source data. 
    Missing or incomplete records may affect the analysis.
    <br/><br/>
    <b>Time Period:</b> Analysis covers the {period} period. Trends may vary across different time periods.
    <br/><br/>
    <b>External Factors:</b> This analysis does not account for external market factors, seasonal variations, 
    or competitive activities that may influence the metrics.
    """
    
    elements.append(Paragraph(assumptions_text, normal_style))
    elements.append(Spacer(1, 0.12*inch))
    
    # RECOMMENDATIONS
    elements.append(Paragraph('Recommendations & Action Items', heading_style))
    
    recommendations = []
    
    if source == 'pakwheels':
        if complaints > 0:
            recommendations.append(f"1. <b>Complaint Resolution:</b> Prioritize addressing the {complaints} identified complaints. Implement a systematic tracking and resolution process.")
        if sentiment_values[1] if len(sentiment_values) > 1 else 0 > sentiment_values[0] if len(sentiment_values) > 0 else 0:
            recommendations.append("2. <b>Sentiment Improvement:</b> Develop strategies to increase positive engagement and reduce negative sentiment through improved customer service.")
        recommendations.append(f"3. <b>Community Engagement:</b> Engage actively with the {unique_authors} authors to build relationships and address concerns proactively.")
        recommendations.append("4. <b>Topic Monitoring:</b> Monitor trending topics to stay relevant and responsive to customer interests.")
        recommendations.append("5. <b>Response Strategy:</b> Implement a systematic response strategy for negative feedback within 24-48 hours.")
        
    elif source == 'whatsapp':
        if complaints > 0:
            recommendations.append(f"1. <b>Complaint Management:</b> Establish a priority system for the {complaints} complaints. Target resolution within 24 hours.")
        recommendations.append(f"2. <b>Query Response:</b> Set response time targets for the {message_values[0] if len(message_values) > 0 else 0} customer queries. Aim for <2 hour response time.")
        recommendations.append("3. <b>FAQ Development:</b> Create comprehensive FAQ documentation for frequently asked questions to reduce response time.")
        recommendations.append("4. <b>Automation:</b> Implement automated responses for common inquiries to improve efficiency and customer satisfaction.")
        recommendations.append("5. <b>Satisfaction Surveys:</b> Schedule regular customer satisfaction surveys to measure improvement.")
    
    for rec in recommendations:
        elements.append(Paragraph(rec, normal_style))
        elements.append(Spacer(1, 0.04*inch))
    
    elements.append(Spacer(1, 0.05*inch))
    
    # OBJECTIVE CONCLUSION
    elements.append(Paragraph('Objective Conclusion', heading_style))
    
    if source == 'pakwheels':
        conclusion_text = f"""
        Based on the analysis of {total_posts} posts from {unique_authors} authors over the {period} period, 
        the following conclusions can be drawn:
        <br/><br/>
        <b>Current State:</b> PakWheels remains an active platform for customer feedback with {unique_topics} distinct topics being discussed. 
        The sentiment distribution shows {round((sentiment_values[0]/max(total_posts, 1))*100, 1)}% positive sentiment, indicating moderate brand perception.
        <br/><br/>
        <b>Key Issues:</b> The {complaints} complaints identified represent critical areas requiring immediate attention. 
        These complaints, if not addressed, may escalate and negatively impact brand reputation.
        <br/><br/>
        <b>Opportunities:</b> The high engagement level ({round(total_posts/max(unique_authors, 1), 2)} posts per author) presents an opportunity 
        to strengthen customer relationships through proactive engagement and issue resolution.
        <br/><br/>
        <b>Required Actions:</b> Immediate implementation of complaint resolution processes and sentiment improvement strategies is recommended. 
        Regular monitoring and reporting should continue to track progress.
        """
    elif source == 'whatsapp':
        conclusion_text = f"""
        Based on the analysis of {total_posts} messages from {unique_authors} customers over the {period} period, 
        the following conclusions can be drawn:
        <br/><br/>
        <b>Current State:</b> WhatsApp communication shows strong customer engagement with {round(total_posts/max(unique_authors, 1), 2)} messages per customer. 
        The message distribution indicates diverse customer needs across queries, complaints, and support requests.
        <br/><br/>
        <b>Satisfaction Indicators:</b> The complaint rate of {round((complaints/max(total_posts, 1))*100, 2)}% suggests areas for improvement. 
        The high volume of queries indicates active customer interest and engagement.
        <br/><br/>
        <b>Operational Efficiency:</b> Current response capabilities need evaluation to ensure timely handling of {message_values[0] if len(message_values) > 0 else 0} queries 
        and {complaints} complaints.
        <br/><br/>
        <b>Strategic Recommendations:</b> Implementation of automated responses, FAQ documentation, and improved response time targets 
        will enhance customer satisfaction and operational efficiency.
        """
    else:
        conclusion_text = f"""
        Based on the analysis of {total_posts} posts from {unique_authors} authors over the {period} period, 
        the following conclusions can be drawn:
        <br/><br/>
        <b>Community Engagement:</b> Reddit shows active community participation with {unique_topics} distinct topics. 
        The engagement level of {round(total_posts/max(unique_authors, 1), 2)} posts per author indicates strong community interest.
        <br/><br/>
        <b>Brand Perception:</b> Sentiment distribution shows {round((sentiment_values[0]/max(total_posts, 1))*100, 1)}% positive sentiment, 
        indicating the current brand perception on the platform.
        <br/><br/>
        <b>Risk Assessment:</b> The {complaints} complaints identified require monitoring and response to prevent reputation damage.
        <br/><br/>
        <b>Strategic Focus:</b> Continued engagement with the community, proactive complaint resolution, and sentiment monitoring 
        are essential for maintaining positive brand presence on Reddit.
        """
    
    elements.append(Paragraph(conclusion_text, normal_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # API USAGE & COST SECTION
    if token_stats:
        elements.append(Paragraph('API Usage & Cost Summary', heading_style))
        
        # Create token usage table
        token_data = [
            ['Metric', 'Value'],
            ['Total Tokens Used', f"{token_stats.get('total_tokens', 0):,}"],
            ['Input Tokens', f"{token_stats.get('total_input_tokens', 0):,}"],
            ['Output Tokens', f"{token_stats.get('total_output_tokens', 0):,}"],
            ['Total Cost (USD)', f"${token_stats.get('total_cost', 0):.4f}"],
            ['Average Tokens/Request', f"{token_stats.get('avg_tokens_per_request', 0):.0f}"],
            ['Total Requests', f"{token_stats.get('request_count', 0):,}"]
        ]
        
        token_table = Table(token_data, colWidths=[2.5*inch, 2*inch])
        token_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#CC0000')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
        ]))
        
        elements.append(token_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # Add cost breakdown by API type if available
        if 'by_api_type' in token_stats and token_stats['by_api_type']:
            elements.append(Paragraph('Cost Breakdown by API Type', subheading_style))
            
            api_data = [['API Type', 'Tokens', 'Cost (USD)']]
            for api_info in token_stats['by_api_type']:
                api_data.append([
                    api_info.get('api_type', 'Unknown'),
                    f"{api_info.get('total_tokens', 0):,}",
                    f"${api_info.get('total_cost', 0):.4f}"
                ])
            
            api_table = Table(api_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
            api_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#CC0000')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
            ]))
            
            elements.append(api_table)
            elements.append(Spacer(1, 0.1*inch))
    
    # Footer
    elements.append(Spacer(1, 0.1*inch))
    footer_text = Paragraph(
        f'<i>This report was automatically generated by HAVAL Enterprise  AI on {datetime.now().strftime("%Y-%m-%d at %H:%M:%S")}</i>',
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#CC0000'), alignment=TA_CENTER)
    )
    elements.append(footer_text)
    
    # Build PDF
    doc.build(elements)
    output.seek(0)
    
    return output
